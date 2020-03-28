from skabenclient.config import DeviceConfig


class LockConfig(DeviceConfig):

    minimal_running = {
        'closed': True,
        'sound': True,
        'blocked': False,
        'card_list': [],
    }

    def __init__(self, config):
        super().__init__(config)
