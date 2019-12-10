import logging
from skabenclient.handlers import DeviceHandler


class LockHandler(DeviceHandler):
    def __init__(self, config):
        super().__init__(config)

    def local_update(self, data):
        try:
            card_list = data.get('card_list')
            if isinstance(card_list, list):
                if len(card_list) == 0:
                    data['card_list'] = ''
                data['card_list'] = ';'.join(card_list)
            data['uid'] = self.config.get('uid')
            super().local_update(data)
            self.commit()
        except:
            self.rollback()

    def reset_device(self):
        super().reset_device()
        logging.debug('resetting with plot\n\t{}'.format(self.dev.plot))
        try:
            if not self.dev.plot.get('sound'):
                self.dev.sound = False
            if self.dev.plot.get('opened'):
                self.dev.lock_timer = None  # drop timer
                self.dev.open()
            else:
                self.dev.close()
        except:
            logging.exception('lock operation error')


