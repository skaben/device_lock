import os
import time
import pytest
import pygame as pg
import wiringpi as wpi

from skabenclient.helpers import make_event
from skabenclient.config import SystemConfig
from skabenclient.loaders import SoundLoader

from ..device import LockDevice
from ..config import LockConfig


@pytest.fixture
def get_port_data():

    def _dec(data):
        filepath = os.path.join('tests', 'res', 'portdata')
        with open(filepath, 'rw') as fh:
            fh.write(data)
            return [r for r in fh]

    return _dec


@pytest.fixture
def get_from_queue():

    def _wrap(queue):
        idx = 0
        while not idx >= 10:
            if not queue.empty():
                yield queue.get()
            else:
                idx += 1
                time.sleep(.1)

    return _wrap


@pytest.fixture(scope='function')
def get_device(monkeypatch, get_config, default_config):

    def _inner(device_config_dict=None,
               system_config_dict=None):
        if not device_config_dict:
            device_config_dict = default_config('dev')
        if not system_config_dict:
            system_config_dict = default_config('sys')

        devcfg = get_config(LockConfig, device_config_dict, 'device_config.yml')
        devcfg.save()

        syscfg = get_config(SystemConfig, default_config('sys'), 'system_config.yml')

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
        device = LockDevice(syscfg, devcfg)
        return device, devcfg, syscfg

    return _inner


def test_device_init(get_device, default_config):
    """ Testing device init procedure
        ...with all those monkeypatches...
    """
    device, devcfg, syscfg = get_device()

    assert device.pin == syscfg.get('pin'), 'missing pin'
    assert device.alert == syscfg.get('alert'), 'missing default alert'
    assert device.config.data == devcfg.data, 'device configuration not empty'
    assert device.port is None, 'gpio setup when init. do not.'


def test_device_close(get_device):
    device, devcfg, syscfg = get_device()
    device.closed = False
    res = device.close()

    assert res == 'close lock'
    assert device.closed is True


def test_device_open(get_device):
    device, devcfg, syscfg = get_device()
    device.closed = True
    res = device.open()

    assert res == 'open lock'
    assert device.closed is not True


def _put_in_int(device, pl):
    """ Helper function for device internal queue testing """
    device.q_int.put(pl)
    return pl


def test_device_close_simple(get_device, monkeypatch):
    device, devcfg, syscfg = get_device()
    monkeypatch.setattr(device, 'state_update', lambda x: _put_in_int(device, x))
    device.closed = False
    res = device.set_closed()
    assert res is not None, 'already closed, doing nothing'
    event = device.q_int.get()
    assert event == res


def test_device_open_simple(get_device, monkeypatch):
    device, devcfg, syscfg = get_device()
    monkeypatch.setattr(device, 'state_update', lambda x: _put_in_int(device, x))
    device.closed = True
    res = device.set_opened()
    assert res is not None, 'already opened, doing nothing'
    event = device.q_int.get()
    assert event == res

freezed_time = int(time.time())

@pytest.mark.parametrize("now, timer, res", [
    (None, 100, 100),
    (freezed_time, 0, freezed_time),
    (freezed_time, 100, freezed_time + 100),
])
def test_device_timer_close(res, now, timer, get_device):
    device, devcfg, syscfg = get_device()
    device.config = {'timer': timer}
    timer_res = device.set_main_timer(now)

    assert timer_res == str(res)


@pytest.mark.parametrize("now, timer, chk, res", [
    (5, 10, 16, True),  # more than ETA, check success
    (5, 10, 14, None),  # less than ETA, check failed
    (None, 100, 105, True),
])
def test_device_timer_check(now, timer, chk, res, get_device):
    device, devcfg, syscfg = get_device()
    device.config = {'timer': timer}
    device.set_main_timer(now)
    timer_chk = device.check_timer("main", chk)

    assert timer_chk == res


def test_device_send_message(get_device, get_from_queue):
    device, devcfg, syscfg = get_device()
    msg = {'test': 'payload'}
    test_event = make_event('device', 'send', msg)
    event = device.send_message(msg)
    expected = list(get_from_queue(syscfg.get('q_int')))

    assert expected, 'missing event'
    assert not len(expected) > 1, 'too many events'
    assert event.data == expected[0].data
    assert event.type == expected[0].type
    assert event.cmd == expected[0].cmd
