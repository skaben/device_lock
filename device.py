import logging
import pygame as pg
import serial
import time
import os
import threading as th
from queue import Queue

import wiringpi as wpi
from skabenclient.helpers import make_event
from skabenclient.loaders import SoundLoader
from skabenclient.device import BaseDevice
from smart_lock.config import LockConfig

try:
    pg.mixer.pre_init()
except Exception:
    logging.exception('pre-init mixer failed: ')

# TODO: sound disable in status closed
# TODO: sound by pin status, not by database


class LockDevice(BaseDevice):

    """ Smart Lock device handler """

    serial_lock = None
    lock_timer = None
    snd = None  # sound module
    closed = None
    running = None
    config_class = LockConfig

    def __init__(self, system_config, device_config_path):
        super().__init__(system_config, device_config_path)
        self.port = None
        self.keypad_data_queue = None
        self.keypad_thread = None
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
                raise Exception(f'gpio_setup failed, cannot start device:\n{e}')

        logging.info('running lock...')
        self.running = True
        self.keypad_data_queue = Queue()
        self.keypad_thread = th.Thread(target=self._serial_read,
                                     name='serial read Thread',
                                     args=(self.port, self.keypad_data_queue,))
        self.keypad_thread.start()
        start_event = make_event('device', 'reload')
        self.q_int.put(start_event)

        while self.running:
            # main routine
            if self.snd:
                if self.config.get('sound') and not self.snd.enabled:
                    self.sound_on()
                elif not self.config.get('sound') and self.snd.enabled:
                    self.sound_off()

                if self.config.get('closed'):
                    # play field sound without interrupts
                    if not self.snd.channels['bg'].get_busy():
                        self.snd.play(sound='field', channel='bg', loops=-1)

            if self.config.get('blocked'):
                continue

            if not self.config.get('closed'):
                # close by timer
                if self.check_timer(int(time.time())):
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
                if self.config.get('sound'):
                    self.snd.enabled = True
                else:
                    self.snd.enabled = None
            if self.config.get('opened'):
                self.lock_timer = None  # drop timer
                self.open()
            else:
                self.close()
        except Exception:
            logging.exception('lock operation error')

    def stop(self):
        """ Full stop """
        wpi.digitalWrite(self.pin, False)
        raise SystemExit

    def set_opened(self, timer=None, ident='system'):
        """ Wrapper for open operation """
        # open from user input
        op = self.open()
        if op:
            if timer:
                self.set_timer(int(time.time()))
            return self.state_update({'closed': False,
                                      'message': f'lock open by {ident}'})

    def set_closed(self, ident='system'):
        """ Wrapper for close operation """
        # closed from user input
        op = self.close()
        if op:
            return self.state_update({'closed': True,
                                      'message': f'lock close by {ident}'})

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
                # self.snd.play(sound='field', channel='bg', delay=1, loops=-1, fade_ms=1200)
            wpi.digitalWrite(self.pin, 1)
            self.closed = True  # state of GPIO
            return 'close lock'

    def parse_data(self, serial_data):
        """ Parse data from keypad """
        data = None

        try:
            data = serial_data.decode('utf-8')
            # logging.debug('get serial: {}'.format(data))
        except Exception:
            logging.exception(f'cannot decode serial: {serial_data}')

        if data:
            input_type = data[2:4]  # keyboard or card
            input_data = str(data[4:]).strip()  # code entered/readed
            if self.serial_lock and input_data == 'CD':
                time.sleep(1)
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

    def check_id(self, _id):
        """ Check id (code or card number) """
        self.result = ''  # additional clearing point
        _id = str(_id).lower()
        logging.debug(f'checking id {_id}')
        if self.config.get('blocked'):
            if self.snd:
                self.snd.play(sound='denied', channel='fg')
                return

        cards = self.config.get('card_list')
        if not cards:
            logging.error('lock ACL is empty - no card codes in DB')
            self.send_message({'message': 'alert',
                               'level': self.alert,
                               'comment': f'badcode {_id} (ACL empty)'})
            if self.snd:
                self.snd.play(sound='denied', channel='fg')
                return

        current_acl = cards.split(';')
        if _id in current_acl:
            if not self.config.get('closed'):
                self.set_closed(ident=_id)
            else:
                if self.snd:
                    self.snd.play(sound='granted', channel='fg')
                self.set_opened(timer=True, ident=_id)
        else:
            if self.snd:
                self.snd.play(sound='denied', channel='fg')
            # sending alert
            event = make_event('device', 'send', {'message': 'alert',
                                                  'level': self.alert,
                                                  'comment': f'badcode {_id}'})
            self.q_int.put(event)
        self.serial_lock = False

    def _serial_read(self, port, queue):
        logging.debug('start listening serial: {}'.format(port))
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
        except:
            logging.exception('failed to initialize sound module')
            snd = None
        return snd

    def sound_off(self):
        if self.snd:
            logging.debug('sound OFF')
            self.snd.fadeout(300)

    def sound_on(self):
        if self.snd:
            logging.debug('sound ON')
            self.snd.enabled = True
        else:
            # todo: report to server
            logging.debug('sound module not initialized')

    def set_timer(self, now: int) -> int:
        if not now:
            now = '0'
        t = int(self.config.get('timer', 0))
        logging.debug('lock timer start counting {}s'.format(t))
        if t <= 0:
            # no timer, lock will remain open until next server update
            self.lock_timer = None
        else:
            self.lock_timer = int(now) + t
        return self.lock_timer

    def check_timer(self, t):
        if self.lock_timer:
            if not t:
                t = 0
            if self.lock_timer < t:
                logging.debug('closing by timer: {} < {}'.format(self.lock_timer, t))
                self.lock_timer = 0
                return True  # mark as working

    def gpio_setup(self):
        """ Setup wiringpi GPIO """
        wpi.wiringPiSetup()
        wpi.pinMode(self.pin, 1)
        wpi.digitalWrite(self.pin, 0)
        time.sleep(.5)
        wpi.digitalWrite(self.pin, 1)
        time.sleep(.1)
        while not self.port:
            try:
                self.port = serial.Serial('/dev/ttyS1')
                self.port.baudrate = 9600
                logging.debug("Connected to /dev/ttyS1")
            except Exception:
                try:
                    self.port = serial.Serial('/dev/ttyAMA1')
                    self.port.baudrate = 9600
                except Exception:
                    logging.exception('cannot connect serial!')
                else:
                    logging.debug("Connected to /dev/ttyAMA1")
            else:
                logging.debug('failed to connect to serial')
            finally:
                time.sleep(.5)
        return self.port
