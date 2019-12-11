import os

import skabenclient as client
from handler import LockHandler
from device import LockDevice

config = client.helpers.get_config()

device = LockDevice(config)
handler = LockHandler(config)

client.start_app(app_config=config,
                 device_handler=device, 
                 event_handler=handler)
