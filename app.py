import os

import skabenclient as client
from handler import LockHandler
from device import LockDevice
from config import config

conf_path = os.path.join('conf', 'config.yml')

device = LockDevice(config)
handler = LockHandler(config)

client.start_app(config=config,
                 device_handler=device,
                 event_handler=handler)
