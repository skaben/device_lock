import os
import pytest

from skabenclient.contexts import Router
from skabenclient.mqtt_client import MQTTClient
from skabenclient.config import DeviceConfig, SystemConfig
from skabenclient.main import start_app

from smart_lock.config import LockConfig
from smart_lock.device import LockDevice, wpi


@pytest.mark.skip(reason="hanging process of unknown source")
def test_app_integrity(get_config, get_root, default_config, monkeypatch):
    """ Starting skaben test """

    app_config_path = os.path.join(get_root, "res", "system_config.yml")
    dev_config_path = os.path.join(get_root, "res", "device_config.yml")

    devcfg = get_config(LockConfig, default_config('dev'), dev_config_path)
    syscfg = get_config(SystemConfig, default_config('sys'), app_config_path)

    monkeypatch.setattr(Router, "start", lambda *a: True)
    monkeypatch.setattr(Router, "join", lambda *a: True)
    monkeypatch.setattr(MQTTClient, "start", lambda *a: True)
    monkeypatch.setattr(MQTTClient, "join", lambda *a: True)
    monkeypatch.setattr(LockDevice, "run", lambda *a: True)
    monkeypatch.setattr(LockDevice, "close", lambda *a: True)
    monkeypatch.setattr(LockDevice, "gpio_setup", lambda *a: True)

    device = LockDevice(syscfg, devcfg)

    start_app(app_config=syscfg,
              device=device)
