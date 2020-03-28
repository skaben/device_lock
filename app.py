import os

from skabenclient.config import SystemConfig
from skabenclient.main import start_app

from device import LockDevice
from config import LockConfig

root = os.path.abspath(os.path.dirname(__file__))

app_config_path = os.path.join(root, 'conf', 'config.yml')
dev_config_path = os.path.join(root, 'conf', 'device.yml')
log_path = os.path.join(root, 'local.log')

if __name__ == "__main__":
    app_config = SystemConfig(app_config_path)
    app_config.logger(file_path=log_path)
    device = LockDevice(app_config, dev_config_path)
    device.gpio_setup()  # pins for laser control and serial interface for keypads
    device.close()  # turn on laser door, closing lock

    start_app(app_config=app_config,
              device=device)
