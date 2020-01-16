import os

from skabenclient.config import SystemConfig
from skabenclient.main import start_app

from device import LockDevice

root = os.path.abspath(os.path.dirname(__file__))
app_config_path = os.path.join(root, 'conf', 'config.yml')

if __name__ == "__main__":
    app_config = SystemConfig(app_config_path, root=root)
    # default device config file is conf/device.yml
    device = LockDevice(app_config)
    device.gpio_setup()  # pins for laser control and serial interface for keypads
    device.close()  # turn on laser door, closing lock

    start_app(app_config=app_config,
              device=device)
