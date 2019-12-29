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

try:
    pg.mixer.pre_init()
except Exception:
    logging.exception('pre-init mixer failed')

# TODO: sound disable in status closed
# TODO: sound by pin status, not by database


class LockDevice:

    """ Smart Lock device handler """

    serial_lock = None
    lock_timer = None
    snd = None
    closed = None
    port = None

    def __init__(self, system_config, device_config):
        self.port = None
        self.plot = device_config
        self.result = ''
        # set config values (without gorillas, bananas and jungles)
        self.uid = system_config.uid
        self.pin = system_config.pin
        self.q_int = system_config.q_int
        self.alert = system_config.alert
        # set sound
        self.snd = self._snd_init(system_config.sound_dir)
        # setup gpio and serial listener
        self.gpio_setup()
        self.data_queue = Queue()
        self.data_thread = th.Thread(target=self._serial_read,
                                     name='serial read Thread',
                                     args=(self.port, self.data_queue,))
        self.close()  # turn on laser door, closing lock

    def run(self):
        """ Running lock """
        logging.info('running lock...')
        self.running = True
        self.data_thread.start()
        start_event = make_event('device', 'reload')
        self.q_int.put(start_event)

        while self.running:
            # reading serial from keypads
            if self.data_queue.empty():
                # main routine
                if self.snd:
                    if self.plot.get('sound') and not self.snd.enabled:
                        self.sound_on()
                    elif not self.plot.get('sound') and self.snd.enabled:
                        self.sound_off()

                    if self.plot.get('closed'):
                        # play field sound without interrupts
                        if not self.snd.channels['bg'].get_busy():
                            self.snd.play(sound='field', channel='bg', loops=-1)

                if self.plot.get('blocked'):
                    continue
                if not self.plot.get('closed'):
                    # close by timer
                    if self.check_timer(int(time.time())):
                        self.set_closed()
                time.sleep(.1)
            else:
                data = self.data_queue.get()
                if data:
                    self.parse_data(data)
        else:
            return self.stop()

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

    def stop(self):
        """ Full stop """
        wpi.digitalWrite(self.pin, False)
        raise SystemExit

    def state_update(self, msg):
        """ Update device configuration from user actions """
        if not isinstance(msg, dict):
            logging.error('message type not dict: {}\n{}'
                          .format(type(msg), msg))
            return
        # self.plot.set('alert', 0)  # resetting alert # TODO: what's happening here??
        # delta_keys used later for sending package to server
        delta = {}
        logging.debug('plot was {}'.format(self.plot))
        for key in msg:
            # make diff
            old_value = self.plot.get(key, None)
            if msg[key] != old_value:
                delta[key] = msg[key]
        self.plot.save(payload=delta)
        # if state changed - send event
        # logging.debug('new user event from {}'.format(delta))
        logging.debug('plot now {}'.format(self.plot))
        if delta:
            delta['uid'] = self.uid
            event = make_event('device', 'input', delta)
            self.q_int.put(event)
            return event
        # else do nothing - for mitigating possible loop in q_int 'device'

    def send_message(self, msg):
        """ Send message to server """
        event = make_event('device', 'send', msg)
        self.q_int.put(event)
        return f'sending message: {msg}'

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

            if self.plot.get('closed'):
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
                                    self.snd.play(sound='block', channel='fg')
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
                            self.snd.play('block', 'fg')
                        self.set_closed()
                elif input_type == 'CD':
                    if self.snd:
                        self.snd.play('block', 'fg')
                    self.serial_lock = True
                    self.set_closed()

    def check_id(self, _id):
        """ Check id (code or card number) """
        self.result = ''  # additional clearing point
        _id = str(_id).lower()
        logging.debug(f'checking id {_id}')
        if self.plot.get('blocked'):
            if self.snd:
                self.snd.play(sound='block', channel='fg')
                return

        cards = self.plot.get('card_list')
        if not cards:
            logging.error('lock ACL is empty - no card codes in DB')
            self.send_message({'message': 'alert',
                               'level': self.alert,
                               'comment': f'badcode {_id} (ACL empty)'})
            if self.snd:
                self.snd.play(sound='block', channel='fg')
                return

        current_acl = cards.split(';')
        if _id in current_acl:
            if not self.plot.get('closed'):
                self.set_closed(ident=_id)
            else:
                self.set_opened(timer=True, ident=_id)
        else:
            if self.snd:
                self.snd.play(sound='block', channel='fg')
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
        t = int(self.plot.get('timer', 0))
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
            time.sleep(1)

