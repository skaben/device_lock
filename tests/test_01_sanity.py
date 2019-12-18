import os
import pytest

from skabenclient import main
from skabenclient.config import Config

from smart_lock.handler import LockHandler
from smart_lock.device import LockDevice

@pytest.mark.skip
def test_start_app(monkeypatch):
    """ Starting app test """

    config_path = os.path.join('conf', 'config.yml')
    config = Config(config_path)

    device = LockDevice(config)
    handler = LockHandler(config)

    monkeypatch.setattr(main.Router, "start", lambda: True)
    monkeypatch.setattr(main.CDLClient, "start", lambda: True)
    monkeypatch.setattr(main.Router, "join", lambda: True)
    monkeypatch.setattr(main.CDLClient, "join", lambda: True)
    monkeypatch.setattr(LockHandler, "run", lambda: True)

    main.start_app(config=config,
                   device_handler=device,
                   event_handler=handler)
