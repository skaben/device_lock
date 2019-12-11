import os

import skabenclient as client
from handler import LockHandler
from device import LockDevice

conf_path = os.path.join('cfg', 'config.yml')
config = client.helpers.get_config(conf_path)

device = LockDevice(config)
handler = LockHandler(config)

client.start_app(app_config=config,
                 device_handler=device, 
                 event_handler=handler)
