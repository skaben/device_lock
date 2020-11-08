import os
import yaml
import pytest
import wiringpi as wpi

from ..device import LockDevice
from ..config import LockConfig
from skabenclient.config import SystemConfig



root_dir = os.path.dirname(os.path.abspath(__file__))


def _iface():
    stream = os.popen("ip route | grep 'default' | sed -nr 's/.*dev ([^\ ]+).*/\\1/p'")
    iface_name = stream.read()
    return iface_name.rstrip()


def write_config(config, fname=None):
    if not fname:
        fname = "config.yml"
    path = os.path.join(root_dir, "res", fname)
    try:
        with open(path, "w") as file:
            yaml.dump(config, file)
        return path
    except Exception:
        raise


@pytest.fixture(scope="module")
def get_root():
    return root_dir


@pytest.fixture(scope="module")
def get_iface():
    return _iface()


@pytest.fixture
def default_config():

    _sys = {
        "dev_type": "test",
        "test": "test",
        "name": "main",
        "broker_ip": "127.0.0.1",
        "iface": _iface()
    }

    _dev = {'bool': True,
            'int': 1,
            'float': 0.1,
            'string': 'abcd',
            'list': [1, 'str', 0.1]}

    initial_config = {
        'closed': True,
        'sound': True,
        'blocked': False,
        'acl': [],
    }

    default_test_config = {
        "acl": ["CODE0"],
        "blocked": False,
        "closed": True,
        "sound": False
    }

    switch = {
        'sys': _sys,
        'dev': _dev,
        'initial': initial_config,
        'default': default_test_config
    }

    def _wrap(conf_type):
        return switch.get(conf_type)

    return _wrap


@pytest.fixture
def get_config(request):
    """ creates config object

        config_obj :
            app config object derived from skabenclient.DeviceConfig
        config_dict : dict
            actual config content
        fname : str
            config file path
    """

    def _wrap(config_obj, config_dict, fname=None):
        path = write_config(config_dict, fname)
        config = config_obj(path)
        config.update(config_dict)

        def _td():
            try:
                os.remove(path)
                os.remove(f"{path}.lock")
            except FileNotFoundError:
                pass
            except Exception:
                raise

        request.addfinalizer(_td)
        return config

    return _wrap


@pytest.fixture
def get_device(request, monkeypatch, get_config, default_config):
    """ Patching all the GPIO out, 'cuz difficult to emulate """

    def _inner(device_config_dict=None,
               system_config_dict=None):

        if not device_config_dict:
            device_config_dict = default_config('dev')

        devcfg = get_config(LockConfig, device_config_dict, 'device_config.yml')
        devcfg.save()

        syscfg = get_config(SystemConfig, default_config('sys'), 'system_config.yml')

        # patch all GPIO operations by default
        monkeypatch.setattr(wpi, "wiringPiSetup", lambda x: True)
        monkeypatch.setattr(wpi, "pinMode", lambda *args: True)
        monkeypatch.setattr(wpi, "digitalWrite", lambda *args: True)
        # patch lock_device
        monkeypatch.setattr(LockDevice, "_serial_read", lambda *args: True)
        # disable GPIO
        monkeypatch.setattr(LockDevice, "gpio_setup", lambda *args: True)
        # disable sound
        monkeypatch.setattr(LockDevice, "_snd_init", lambda *args: None)
        # monkeypatch.setattr(LockDevice, "port", get_port_data)
        device = LockDevice(syscfg, devcfg)

        print(f"another one config: {devcfg}")

        return device, devcfg, syscfg

    return _inner


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


@pytest.fixture
def device_run(request):

    def _wrap(device):

        device.run()

        def _td():
            try:
                device.stop()
            except Exception:
                raise

        request.addfinalizer(_td)
        return result

    return _wrap

