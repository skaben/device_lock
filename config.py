from skabenclient.config import DeviceConfig

ESSENTIAL = {
    'closed': True,
    'sound': True,
    'blocked': False,
    'card_list': [],
}


class LockConfig(DeviceConfig):

    def __init__(self, config):
        self.minimal_essential_conf = ESSENTIAL
        super().__init__(config)
