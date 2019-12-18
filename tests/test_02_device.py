import os
import time
import pytest
import pygame as pg
import wiringpi as wpi

from skabenclient.helpers import make_event
from skabenclient.config import Config
from smart_lock.device import LockDevice


@pytest.fixture
def get_port_data():

    def _dec(data):
        filepath = os.path.join('tests', 'res', 'portdata')
        with open(filepath, 'rw') as fh:
            fh.write(data)
            return [r for r in fh]

    return _dec


@pytest.fixture(scope='function')
def get_device(monkeypatch):

    def _inner(config):
        # monkey patch all GPIO operations by default
        monkeypatch.setattr(wpi, "wiringPiSetup", lambda x: True)
        monkeypatch.setattr(wpi, "pinMode", lambda *args: True)
        monkeypatch.setattr(wpi, "digitalWrite", lambda *args: True)
        # monkey patch lock_device
        monkeypatch.setattr(LockDevice, "_serial_read", lambda *args: True)
        # disable GPIO
        monkeypatch.setattr(LockDevice, "gpio_setup", lambda *args: True)
        # disable sound
        monkeypatch.setattr(LockDevice, "_snd_init", lambda *args: None)
        # monkeypatch.setattr(LockDevice, "port", get_port_data)
        device = LockDevice(config)
        return device

    return _inner


def test_device_init(get_device):
    """ Testing device init procedure
        ...with all those monkeypatches...
    """
    config = Config(os.path.join('tests', 'res', 'config.yml'))
    device = get_device(config)

    assert device.plot == {}
    assert device.port is None


def test_device_close(get_device):
    config = Config(os.path.join('tests', 'res', 'config.yml'))
    device = get_device(config)
    device.closed = False
    res = device.close()

    assert res == 'close lock'
    assert device.closed is True


def test_device_open(get_device):
    config = Config(os.path.join('tests', 'res', 'config.yml'))
    device = get_device(config)
    device.closed = True
    res = device.open()

    assert res == 'open lock'
    assert device.closed is not True


def _put_in_int(device, pl):
    """ Helper function for device internal queue testing """
    device.q_int.put(pl)
    return pl


def test_device_close_simple(get_device, monkeypatch):
    config = Config(os.path.join('tests', 'res', 'config.yml'))
    device = get_device(config)
    monkeypatch.setattr(device, 'state_update', lambda x: _put_in_int(device, x))
    device.closed = False
    res = device.set_closed()
    assert res is not None, 'already closed, doing nothing'
    event = device.q_int.get()
    assert event == res


def test_device_open_simple(get_device, monkeypatch):
    config = Config(os.path.join('tests', 'res', 'config.yml'))
    device = get_device(config)
    monkeypatch.setattr(device, 'state_update', lambda x: _put_in_int(device, x))
    device.closed = True
    res = device.set_opened()
    assert res is not None, 'already opened, doing nothing'
    event = device.q_int.get()
    assert event == res


def test_device_send_message(get_device):
    config = Config(os.path.join('tests', 'res', 'config.yml'))
    device = get_device(config)
    msg = {'test': 'payload'}
    test_event = make_event('device', 'send', msg)
    res = device.send_message(msg)

    assert res == f'sending message: {msg}'
    assert device.q_int.get().__dict__ == test_event.__dict__


@pytest.mark.parametrize("now, timer, res", [
    (0, 10, 10),
    (None, 100, 100),
    (int(time.time()), 0, None),
])
def test_device_timer_pos(get_device, now, timer, res):
    config = Config(os.path.join('tests', 'res', 'config.yml'))
    device = get_device(config)
    device.plot = {'timer': timer}
    timer_res = device.set_timer(now)

    assert timer_res == res


@pytest.mark.parametrize("now, timer, chk, res", [
    (5, 10, 16, True),  # more than ETA, check success
    (5, 10, 14, None),  # less than ETA, check failed
    (None, 100, 105, True),  # None as 0
])
def test_device_timer_check(get_device, now, timer, chk, res):
    config = Config(os.path.join('tests', 'res', 'config.yml'))
    device = get_device(config)
    device.plot = {'timer': timer}
    device.set_timer(now)
    timer_chk = device.check_timer(chk)

    assert timer_chk == res
