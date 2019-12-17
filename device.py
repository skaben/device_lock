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

    serial_lock = None
    lock_timer = None
    sound = None
    snd = None
    opened = None

    def __init__(self, config):
        self.port = None
        self.plot = dict()
        self.result = ''
        # set config values (without gorillas, bananas and jungles)
        self.uid = config.uid
        self.pin = config.pin
        self.q_int = config.q_int
        self.alert = config.alert
        self.snd = SoundLoader(config.sound_dir)
        # setup gpio and serial listener
        self.gpio_setup()
        self.data_queue = Queue()
        self.data_thread = th.Thread(target=self._serial_read,
                                     name='serial read Thread',
                                     args=(self.port, self.data_queue,))
        self.close()  # turn on laser door, closing lock

    def _serial_read(self, port, queue):
        logging.debug('start listening serial: {}'.format(port))
        while self.running:
            # serial_data = wpi.serialGetchar(port)
            serial_data = port.readline()
            if serial_data:
                queue.put(serial_data)
            else:
                time.sleep(.1)

    def sound_off(self):
        self.sound = None
        if self.sndm:
            logging.debug('sound OFF')
            for ch in self.sndm.channels:
                ch.fadeout(300)

    def sound_on(self):
        if not pg.mixer.get_init():
            pg.mixer.quit()
            self.pg_mixer_reinit()
        if self.sndm.enabled:
            logging.debug('sound ON')
            self.sound = True

    def set_timer(self):
        t = int(self.plot.get('timer'))
        logging.debug('lock timer start counting {}s'.format(t))
        if t <= 0:
            # no timer, lock will remain open until next server update
            self.lock_timer = None
            return True
        else:
            self.lock_timer = int(time.time()) + t

    def check_timer(self, t):
        if self.lock_timer and self.lock_timer < t:
            logging.debug('closing by timer: {} < {}'
                          .format(self.lock_timer, t))
            self.lock_timer = None
            return True

    def gpio_setup(self):
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

    def send_message(self, msg):
        logging.debug(f'sending message: {msg}')
        event = make_event('device', 'send', msg)
        self.q_int.put(event)

    def state_update(self, msg):
        """
            update state by user input
            msg: {'blocked': True}
        """
        if not isinstance(msg, dict):
            logging.error('message type not dict: {}\n{}'
                          .format(type(msg), msg))
            return
        self.plot['alert'] = 0  # resetting alert
        # delta_keys used later for sending package to server
        delta = {}
        logging.debug('plot was {}'.format(self.plot))
        for key in msg:
            # make diff
            old_value = self.plot.get(key, None)
            if msg[key] != old_value:
                self.plot[key] = msg[key]  # direct update without manager
                delta[key] = msg[key]
        # if state changed - send event
        # logging.debug('new user event from {}'.format(delta))
        logging.debug('plot now {}'.format(self.plot))
        if delta:
            delta['uid'] = self.uid
            event = make_event('device', 'input', delta)
            self.q_int.put(event)
        # else do nothing - for mitigating possible loop in q_int 'device'

    def set_opened(self, timer=None, ident='system'):
        if self.opened:
            return

        # open from user input
        self.open()
        self.state_update({'opened': True,
                           'message': f'lock open by {ident}'})
        if timer:
            self.set_timer()

    def set_closed(self, ident='system'):
        if not self.opened:
            return

        # closed from user input
        self.close()
        self.state_update({'opened': False,
                           'message': f'lock close by {ident}'})

    def open(self):
        logging.debug('open lock')
        if self.sound:
            self.channel_bg.fadeout(1200)
            self.channel_fg.play(self.snd_off)
            time.sleep(1.5)
        wpi.digitalWrite(self.pin, 0)
        self.opened = True  # state of GPIO
        # additional field sound check
        if self.channel_bg.get_busy():
            self.channel_bg.stop()  # force stop

    def close(self):
        logging.debug('close lock')
        if self.sound:
            self.channel_fg.play(self.snd_on)
            time.sleep(.5)
            self.channel_bg.play(self.snd_field, loops=-1, fade_ms=1200)
            time.sleep(1)
        wpi.digitalWrite(self.pin, 1)
        self.opened = False  # state of GPIO

    def check_id(self, _id):
        self.result = ''  # additional clearing point
        _id = str(_id).lower()
        logging.debug(f'checking id {_id}')
        if self.plot.get('blocked'):
            if self.sound:
                self.channel_fg.play(self.snd_block)
                return

        cards = self.plot.get('card_list')
        if not cards:
            logging.error('lock ACL is empty - no card codes in DB')
            self.send_message({'message': 'alert',
                               'level': self.alert,
                               'comment': f'badcode {_id} (ACL empty)'})
            if self.sound:
                self.channel_fg.play(self.snd_block)
                return

        current_acl = cards.split(';')
        if _id in current_acl:
            if self.plot.get('opened'):
                self.set_closed(ident=_id)
            else:
                self.set_opened(timer=True, ident=_id)
        else:
            if self.sound:
                self.channel_fg.play(self.snd_block)
            # sending alert
            event = make_event('device', 'send', {'message': 'alert',
                                                  'level': self.alert,
                                                  'comment': f'badcode {_id}'})
            self.q_int.put(event)
        self.serial_lock = False

    def stop(self):
        wpi.digitalWrite(self.pin, False)
        raise SystemExit

    def run(self):
        logging.info('running lock...')
        self.running = True
        self.data_thread.start()
        start_event = make_event('device', 'reload')
        self.q_int.put(start_event)

        while self.running:
            # reading serial from keypads
            if self.data_queue.empty():
                # main routine
                if self.plot.get('sound') and not self.sound:
                    self.sound_on()
                elif not self.plot.get('sound') and self.sound:
                    self.sound_off()

                if self.sound:
                    if not self.plot.get('opened'):
                        if not self.channel_bg.get_busy():
                            self.channel_bg.play(self.snd_field, loops=-1)

                if self.plot.get('blocked'):
                    continue
                if self.plot.get('opened'):
                    # is it time to close?
                    if self.check_timer(int(time.time())):
                        self.set_closed()
                time.sleep(.1)
            else:
                data = self.data_queue.get()
                if data:
                    self.parse_data(data)
        else:
            return self.stop()

    def parse_data(self, serial_data):
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

            if not self.plot.get('opened'):
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
                                if self.sound:
                                    self.channel_fg.play(self.snd_block)
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
                        if self.sound:
                            self.channel_fg.play(self.snd_block)
                        self.set_closed()
                elif input_type == 'CD':
                    if self.sound:
                        self.channel_fg.play(self.snd_block)
                    self.serial_lock = True
                    self.set_closed()
