import os

from skabenclient.config import SystemConfig
from skabenclient.main import start_app

from device import LockDevice
from config import LockConfig

root = os.path.abspath(os.path.dirname(__file__))

sys_config_path = os.path.join(root, 'conf', 'system.yml')
dev_config_path = os.path.join(root, 'conf', 'device.yml')

if __name__ == "__main__":
    # setting up system configuration and logger
    app_config = SystemConfig(sys_config_path)
    dev_config = LockConfig(dev_config_path)
    device = LockDevice(app_config, dev_config)
    device.gpio_setup()  # pins for laser control and serial interface for keypads
    start_app(app_config=app_config,
              device=device)
