import os

import skabenclient as client
from handler import LockHandler
from device import LockDevice

config_path = os.path.join('conf', 'config.yml')
config = client.Config(config_path)

device = LockDevice(config)
handler = LockHandler(config)

client.start_app(config=config,
                 device_handler=device,
                 event_handler=handler)
