from skabenclient.config import DeviceConfig

ESSENTIAL = {
    'closed': True,
    'sound': True,
    'blocked': False,
    'acl': [],
}


class LockConfig(DeviceConfig):

    def __init__(self, config_path):
        self.minimal_essential_conf = ESSENTIAL
        super().__init__(config_path)
