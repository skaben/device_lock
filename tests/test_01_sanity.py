import os
import pytest

from skabenclient import main
from skabenclient.config import DeviceConfig, SystemConfig

from smart_lock.device import LockDevice, wpi


def test_app_integrity(get_config, get_root, default_config, monkeypatch):
    """ Starting app test """

    app_config_path = os.path.join(get_root, "res", "app_config.yml")
    dev_config_path = os.path.join(get_root, "res", "dev_config.yml")

    devcfg = get_config(DeviceConfig, default_config('dev'), dev_config_path)
    syscfg = get_config(SystemConfig, default_config('sys'), app_config_path)

    monkeypatch.setattr(main.EventRouter, "start", lambda *a: True)
    monkeypatch.setattr(main.EventRouter, "join", lambda *a: True)
    monkeypatch.setattr(main.MQTTClient, "start", lambda *a: True)
    monkeypatch.setattr(main.MQTTClient, "join", lambda *a: True)
    monkeypatch.setattr(LockDevice, "run", lambda *a: True)
    monkeypatch.setattr(LockDevice, "close", lambda *a: True)
    monkeypatch.setattr(LockDevice, "gpio_setup", lambda *a: True)

    device = LockDevice(syscfg, devcfg.config_path)

    main.start_app(app_config=syscfg,
                   device=device)
