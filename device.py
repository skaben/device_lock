import pygame as pg
import serial
import time
import threading as th
from queue import Queue

import wiringpi as wpi
from skabenclient.helpers import make_event
from skabenclient.loaders import SoundLoader
from skabenclient.device import BaseDevice
from config import LockConfig

try:
    pg.mixer.pre_init()
except Exception:
    self.logger.exception('pre-init mixer failed: ')


class LockDevice(BaseDevice):

    """ Smart Lock device handler """

    serial_lock = None
    snd = None # sound module
    closed = None
    running = None
    unlock_attempts = []
    config_class = LockConfig

    def __init__(self, system_config, device_config):
        super().__init__(system_config, device_config)
        self.port = None
        self.keypad_data_queue = None
        self.keypad_thread = None
        self.timers = {}
        self.result = ''
        # set config values (without gorillas, bananas and jungles)
        self.pin = system_config.get('pin')
        self.alert = system_config.get('alert')
        # set sound
        self.snd = self._snd_init(system_config.get('sound_dir'))

    def run(self):
        """ Running lock

            self.gpio_setup() must be performed before run
        """
        if not self.port:
            try:
                self.gpio_setup()
            except Exception as e:
                self.logger.exception(f'gpio_setup failed, cannot start device:\n{e}')
                raise

        self.logger.info('running lock...')
        self.running = True
        self.keypad_data_queue = Queue()
        self.keypad_thread = th.Thread(target=self._serial_read,
                                       name='serial read Thread',
                                       args=(self.port, self.keypad_data_queue,))
        self.keypad_thread.start()
        start_event = make_event('device', 'reload')
        self.q_int.put(start_event)
        acl = self.config.get("acl")
        self.logger.info(f"current ACL is {acl}")

        if self.config.get("sound"):
            self.snd.enabled = True
        else:
            self.snd.enabled = None

        while self.running:
            # main routine
            if self.snd:
                self.manage_sound()

            if self.config.get('blocked'):
                continue

            if not self.config.get('closed'):
                # close by timer
                if self.check_timer("main", int(time.time())):
                    self.set_closed()

            if not self.keypad_data_queue.empty():
                # reading serial from keypads
                data = self.keypad_data_queue.get()
                if data:
                    self.parse_data(data)
            else:
                time.sleep(.1)

        else:
            return self.stop()

    def reset(self):
        """ Resetting from saved config """
        super().reset()
        try:
            if self.snd:
                self.snd.enabled = self.config.get('sound')
            if not self.config.get('closed'):
                self.timers = {}
                self.open()
            else:
                self.close()
        except Exception:
            self.logger.exception('lock operation error')

    def stop(self):
        """ Full stop """
        wpi.digitalWrite(self.pin, False)
        raise SystemExit

    def open(self):
        """ Open lock """
        if self.closed:
            if self.snd:
                self.snd.fadeout(1200, 'bg')
                self.snd.play(sound='off', channel='fg', delay=1.5)
            wpi.digitalWrite(self.pin, 0)
            self.closed = False  # state of GPIO
            # additional field sound check
            if self.snd:
                self.snd.stop('bg')
            return 'open lock'

    def close(self):
        """ Close lock """
        if not self.closed:
            if self.snd:
                self.snd.play(sound='on', channel='fg', delay=.5)
                self.snd.play(sound='field', channel='bg', delay=1, loops=-1, fade_ms=1200)
            wpi.digitalWrite(self.pin, 1)
            self.closed = True  # state of GPIO
            return 'close lock'

    def set_opened(self, timer=None, ident=None):
        """ Wrapper for open operation """
        # open from user input
        op = self.open()
        if op:
            if ident:
                self.logger.info(f"[---] OPEN by {ident}")
            if timer:
                now = int(time.time())
                self.set_main_timer(now)
            return self.state_update({"closed": False})

    def set_closed(self, ident='system'):
        """ Wrapper for close operation """
        # closed from user input
        op = self.close()
        if op:
            self.logger.info(f"[---] CLOSE by {ident}")
            return self.state_update({'closed': True})

    def check_id(self, _id):
        """ Check id (code or card number) """
        self.result = ''  # additional clearing point
        code = str(_id).lower()
        self.logger.debug(f'checking id {code}')

        if self.config.get('blocked'):
            return self.access_denied(code)

        self.is_id_in_acl(code, self.config.get('acl'))
        self.serial_lock = False

    def is_id_in_acl(self, code, acl):
        if not acl:
            self.logger.error('lock ACL is empty - no card codes in DB')
            return self.access_denied()
        closed = self.config.get("closed")
        if code in acl:
            if closed:
                return self.access_granted(code)
            else:
                return self.set_closed(ident=code)
        else:
            return self.access_denied(code)

    def access_denied(self, code=None):
        if self.snd:
            self.snd.play(sound='denied', channel='fg')
        if code:
            self.logger.info(f"[---] DENIED to {code}")
            self.unlock_attempts.append(code)
        time.sleep(.3)

    def access_granted(self, code):
        if self.snd:
            self.snd.play(sound='granted', channel='fg')
        return self.set_opened(timer=True, ident=code)

    def sound_off(self):
        if self.snd:
            self.logger.debug('sound OFF')
            try:
                self.snd.fadeout(300)
            except:
                self.snd.stop()
                self.snd.enabled = None

    def sound_on(self):
        if self.snd:
            self.logger.debug('sound ON')
            self.snd.enabled = True
        else:
            self.send_message({"error": "sound module init failed"})
            self.logger.debug('sound module not initialized')

    def manage_sound(self):
        sound = self.config.get("sound")
        if sound and not self.snd.enabled:
            self.sound_on()
        elif not sound and self.snd.enabled:
            self.sound_off()
        else:
            return

        if self.config.get('closed'):
            # play field sound without interrupts
            if not self.snd.channels['bg'].get_busy():
                self.snd.play(sound='field', channel='bg', loops=-1)

    def set_main_timer(self, now: int) -> str:
        delay = self.config.get('timer')
        if delay:
            self.logger.debug('lock timer start counting {}s'.format(delay))
            return self.new_timer(now, delay, "main")
        else:
            self.logger.error("no time interval for auto timer set! check config.")

    def new_timer(self, now: int, value: str, name: str) -> str:
        if int(value) > 0:
            new_value = int(now) + int(value)
            self.timers.update({name: new_value})
            self.logger.debug(f"timer set at {now} with name {name} to {value}s")
            return self.timers[name]
        else:
            self.logger.debug(f"timer set too close: {value} < 0")

    def check_timer(self, name: str, now: int) -> bool:
        timer = self.timers.get(name)
        if not timer:
            self.logger.error(f"no such timer {timer}")
            return

        if int(timer) <= int(now):
            return self.timers.pop(name)

    def gpio_setup(self):
        """ Setup wiringpi GPIO """
        wpi.wiringPiSetup()
        wpi.pinMode(self.pin, 1)
        wpi.digitalWrite(self.pin, 0)
        time.sleep(.5)
        while not self.port:
            try:
                self.port = serial.Serial('/dev/ttyS1')
                self.port.baudrate = 9600
                self.logger.debug("Connected to /dev/ttyS1")
            except Exception:
                try:
                    self.port = serial.Serial('/dev/ttyAMA1')
                    self.port.baudrate = 9600
                except Exception:
                    self.logger.exception('cannot connect serial!')
                else:
                    self.logger.debug("Connected to /dev/ttyAMA1")
            else:
                self.logger.debug('failed to connect to serial')
            finally:
                time.sleep(.5)
        return self.port

    def parse_data(self, serial_data):
        """ Parse data from keypad """
        data = None

        try:
            data = serial_data.decode('utf-8')
            # self.logger.debug('get serial: {}'.format(data))
        except Exception:
            self.logger.exception(f'cannot decode serial: {serial_data}')
            self.access_denied()
            time.sleep(5)

        if data:
            input_type = data[2:4]  # keyboard or card
            input_data = str(data[4:]).strip()  # code entered/readed
            if self.serial_lock and input_data == 'CD':
                time.sleep(.5)
                self.serial_lock = False
                return

            if self.config.get('closed'):
                # lock CLOSED
                # keyboard event registered
                if input_type == 'KB':
                    if int(input_data) == 10:
                        self.result = ''
                    else:
                        if int(input_data) == 11:
                            try:
                                self.check_id(self.result)
                            except Exception:
                                if self.snd:
                                    self.snd.play(sound='denied', channel='fg')
                        else:
                            self.result += str(input_data)
                elif input_type == 'CD':
                    self.serial_lock = True
                    # card action registered
                    self.check_id(input_data)
                    self.result = ''
            else:
                # lock OPENED
                if input_type == 'KB':
                    if int(input_data) == 11:
                        if self.snd:
                            self.snd.play('denied', 'fg')
                        self.set_closed()
                elif input_type == 'CD':
                    if self.snd:
                        self.snd.play('denied', 'fg')
                    self.serial_lock = True
                    self.set_closed()

    def _serial_read(self, port, queue):
        self.logger.debug('start listening serial: {}'.format(port))
        while self.running:
            # serial_data = wpi.serialGetchar(port)
            serial_data = port.readline()
            if serial_data:
                queue.put(serial_data)
            else:
                time.sleep(.1)

    def _snd_init(self, sound_dir):
        try:
            snd = SoundLoader(sound_dir=sound_dir)
        except Exception:
            self.logger.exception('failed to initialize sound module')
            snd = None
        return snd
