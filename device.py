import pygame as pg
import serial
import logging
import time
import threading as th

from typing import Union, Optional
from queue import Queue

import wiringpi as wpi
from skabenclient.helpers import make_event
from skabenclient.loaders import SoundLoader
from skabenclient.device import BaseDevice
from skabenclient.config import SystemConfig
from config import LockConfig

try:
    pg.mixer.pre_init()
except Exception:
    logging.exception('pre-init mixer failed: ')


DEFAULT_SLEEP = .5  # 500ms
SOUND_FADEOUT = 300  # 300ms
SERIAL_TIMEOUT = 1
DEFAULT_TIMER_TIME = 10

CARD_EVENT = 'CD'
KBD_EVENT = 'KB'


class LockDevice(BaseDevice):

    """ Smart Lock device """

    result = ''  # read from serial
    serial_lock = None
    snd = None  # sound module
    closed = None
    running = None
    config_class = LockConfig

    def __init__(self, system_config: SystemConfig, device_config: LockConfig):
        super().__init__(system_config, device_config)
        self.port = None
        self.keypad_thread = None
        self.keypad_data_queue = Queue()
        self.timers = {}
        # set config values (without gorillas, bananas and jungles)
        self.pin = system_config.get('pin')
        self.alert = system_config.get('alert')
        self.preferred_serial = system_config.get('comport', '/dev/ttyS1')
        # set sound
        self.snd = self._snd_init(system_config.get('sound_dir'))
        self.logger.debug(f'{self.config.get("acl")}')

    def on_start(self):
        """initialize serial listener, reload device"""
        if not self.port:
            try:
                self.gpio_setup()
            except Exception as e:
                self.logger.exception(f'gpio_setup failed, cannot start device:\n{e}')
                raise

        self.keypad_thread = th.Thread(target=self._serial_read,
                                       name='serial read Thread',
                                       args=(self.port, self.keypad_data_queue,))
        self.keypad_thread.daemon = True

    def run(self):
        """ Running lock

            self.gpio_setup() must be performed before run
        """
        self.on_start()
        self.logger.info('running lock...')
        start_event = make_event('device', 'reload')
        self.q_int.put(start_event)
        self.running = True
        self.keypad_thread.start()

        while self.running:
            # main routine
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
                time.sleep(DEFAULT_SLEEP / 5)

        else:
            return self.stop()

    def reset(self):
        """ Resetting from saved config """
        self.logger.debug(f"running with config: {self.config.data}")
        try:
            if self.snd:
                self.snd.enabled = self.config.get('sound')
            if not self.config.get('closed'):
                self.timers = {}  # drop timer
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
        """Open lock low-level operation"""
        if self.closed:
            if self.sound_enabled:
                self.snd.fadeout(SOUND_FADEOUT * 4, 'bg')
                self.snd.play(sound='off', channel='fg', delay=DEFAULT_SLEEP * 3)
            time.sleep(DEFAULT_SLEEP * 2)
            wpi.digitalWrite(self.pin, False)
            self.closed = False  # state of GPIO
            # additional field sound check
            if self.snd:
                self.snd.stop('bg')
            return 'open lock'

    def close(self):
        """Close lock low-level operation"""
        if not self.closed:
            if self.sound_enabled:
                self.snd.play(sound='on', channel='fg', delay=DEFAULT_SLEEP)
                self.snd.play(sound='field', channel='bg', delay=DEFAULT_SLEEP * 2, loops=-1, fade_ms=SOUND_FADEOUT * 4)
            wpi.digitalWrite(self.pin, True)
            self.closed = True  # state of GPIO
            return 'close lock'

    def set_opened(self, timer: Optional[bool] = None, code: Optional[str] = None):
        """Open lock with config update and timer"""
        if self.open():
            if code:
                self.logger.info(f"[---] OPEN by {code}")
            if timer:
                self.new_timer(int(time.time()), self.config.get('timer', DEFAULT_TIMER_TIME), "main")
            return self.state_update({"closed": False})

    def set_closed(self, code: Optional[str] = 'system'):
        """Close lock with config update"""
        if self.close():
            self.logger.info(f"[---] CLOSE by {code}")
            return self.state_update({'closed': True})

    def access_granted(self, code: str):
        """Direct User Interaction access granted"""
        if self.sound_enabled:
            self.snd.play(sound='granted', channel='fg')
        self.send_message({"message": f"{code} granted"})
        return self.set_opened(timer=True, code=code)

    def access_denied(self, code: Optional[str] = None):
        """Direct User Interaction access denied"""
        if self.sound_enabled:
            self.snd.play(sound='denied', channel='fg')
        if code:
            self.logger.info(f"[---] DENIED to {code}")
            self.send_message({"message": f"{code} denied"})
        time.sleep(DEFAULT_SLEEP)
        return self.set_closed()

    def check_access(self, code: str):
        """ Check id (code or card number) """
        self.logger.debug(f'checking id: {code}')
        try:
            # in blocked state lock should deny everything
            if self.config.get('blocked'):
                return self.access_denied(code)
            # in opened state lock should close on every code
            if not self.config.get('closed'):
                return self.set_closed(code)

            acl = [str(c) for c in self.config.get('acl')]
            if not acl:
                raise AttributeError('lock ACL is empty - no card codes in DB')

            if code in acl:
                return self.access_granted(code)
            else:
                return self.access_denied(code)
        except Exception:
            logging.exception(f'while checking id: {code}')
            return self.access_denied(code)
        finally:
            time.sleep(DEFAULT_SLEEP)
            self._serial_clean()

    def parse_data(self, serial_data: bin):
        """ Parse data from keypad """
        data = None

        try:
            data = serial_data.decode('utf-8')
            if not data:
                return
        except Exception:
            self.logger.exception(f'cannot decode serial: {serial_data}')
            self.access_denied()
            time.sleep(DEFAULT_SLEEP * 10)
            return

        try:
            input_type = str(data[2:4])  # keyboard or card
            input_data = str(data[4:]).strip()  # code entered/readed

            print(f'result: {self.result} --- {input_data} {input_type}')

            if self.config.get('closed'):
                self.check_on_input_when_closed(input_type, input_data)
            else:
                self.close_on_input_when_opened(input_type, input_data)
        except Exception:
            self.logger.exception('while operating with controller:')

    def check_on_input_when_closed(self, input_type: str, input_data: str):
        asterisk_button = '10'
        hash_button = '11'
        if input_type == KBD_EVENT:
            if input_data != asterisk_button:
                if input_data == hash_button:
                    try:
                        self.check_access(self.result)
                    except Exception:
                        if self.sound_enabled:
                            self.snd.play(sound='denied', channel='fg')
                else:
                    self.result += input_data
            else:
                self._serial_clean()
        elif input_type == CARD_EVENT:
            if self.serial_lock:
                return
            self.serial_lock = True
            self.check_access(input_data)

    def close_on_input_when_opened(self, input_type: str, input_data: str):
        if input_type == KBD_EVENT:
            # close on # button
            if int(input_data) == 11:
                if self.sound_enabled:
                    self.snd.play('denied', 'fg')
                self.set_closed()
        elif input_type == CARD_EVENT:
            if self.serial_lock:
                return
            self.serial_lock = True
            if self.sound_enabled:
                self.snd.play('denied', 'fg')
            self.set_closed()
        self._serial_clean()

    def sound_off(self):
        if self.snd:
            self.logger.debug('sound OFF')
            for channel in self.snd.channels:
                self.snd.stop(channel)
            self.snd.enabled = None

    def sound_on(self):
        if self.snd:
            self.logger.debug('sound ON')
            self.snd.enabled = True
        else:
            self.send_message({"error": "sound module init failed"})
            self.logger.debug('sound module not initialized')

    @property
    def sound_enabled(self):
        if self.snd and self.snd.enabled:
            return True

    def manage_sound(self):
        if not self.snd:
            return

        sound = self.config.get("sound")
        if sound and not self.snd.enabled:
            self.sound_on()
        elif not sound and self.snd.enabled:
            self.sound_off()
        else:
            return

        if self.config.get('closed'):
            # play field sound without interrupts
            if self.sound_enabled and not self.snd.channels['bg'].get_busy():
                self.snd.play(sound='field', channel='bg', loops=-1)

    def connect_serial(self):
        self.logger.debug(f"Connecting to serial {self.preferred_serial}...")
        port = serial.Serial(self.preferred_serial, timeout=SERIAL_TIMEOUT)
        port.baudrate = 9600
        time.sleep(DEFAULT_SLEEP)
        if port:
            return port
        else:
            self.logger.debug(f'Failed to connect to serial {self.prefferred_serial}')

    def gpio_setup(self):
        """ Setup wiringpi GPIO """
        port = None
        wpi.wiringPiSetup()
        wpi.pinMode(self.pin, 1)
        wpi.digitalWrite(self.pin, 0)
        while not port:
            time.sleep(DEFAULT_SLEEP)
            try:
                port = self.connect_serial()
            except Exception:
                self.preferred_serial = 'dev/ttyAMA1'
                port = self.connect_serial()

        if port:
            self.port = port
            return self.port
        else:
            raise Exception('no serial port connection acquired, exiting')

    def _serial_read(self, port: serial.Serial, queue: Queue):
        self.logger.debug('start listening serial: {}'.format(port))
        while True:
            serial_data = port.readline()
            if serial_data:
                self.logger.debug(f'new data from serial: {serial_data}')
                queue.put(serial_data)
            else:
                time.sleep(DEFAULT_SLEEP / 5)

    def _serial_clean(self):
        self.result = ''
        self.serial_lock = None

    def _snd_init(self, sound_dir: str) -> Union[SoundLoader, None]:
        # TODO: when init failed SoundLoader should return itself with disable=True
        try:
            snd = SoundLoader(sound_dir=sound_dir)
        except Exception:
            self.logger.exception('failed to initialize sound module')
            snd = None
        return snd
