import logging

from skabenclient.config import DeviceConfig


# TODO: naming handler to config
class LockHandler(DeviceConfig):
    def __init__(self, config_path):
        super().__init__(config_path)
        self.data = self.load()

    def local_update(self, data):
        """ TODO: rewrite totally """
        try:
            card_list = data.get('card_list')
            # TODO: Whaaaaa?
            # if isinstance(card_list, list):
            #     data['card_list'] = card_list
            self.save(data)
        except Exception:
            raise

    def reset_device(self):
        """ Resetting from saved config """
        super().load()
        logging.debug('resetting with plot\n\t{}'.format(self.dev.plot))
        try:
            if not self.dev.plot.get('sound'):
                self.dev.sound = False
            if self.dev.plot.get('opened'):
                self.dev.lock_timer = None  # drop timer
                self.dev.open()
            else:
                self.dev.close()
        except Exception:
            logging.exception('lock operation error')
