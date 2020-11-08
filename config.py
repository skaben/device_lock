from skabenclient.config import DeviceConfig

ESSENTIAL = {
    'closed': True,
    'sound': True,
    'blocked': False,
    'acl': ['0000',],
}


class LockConfig(DeviceConfig):

    def __init__(self, config_path):
        self.minimal_essential_conf = ESSENTIAL
        super().__init__(config_path)
