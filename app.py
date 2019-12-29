import os

from skabenclient.config import Config
from skabenclient.main import start_app

from config import LockHandler
from device import LockDevice

config_path = os.path.join('conf', 'config.yml')
config = Config(config_path)

if __name__ == "__main__":
    device = LockDevice(config)
    handler = LockHandler(config)

    start_app(config=config,
              device=device,
              event_handler=handler)
