import os.path as op
from skabenclient.config import Config

config = Config()
config.update({
    'sound_dir': op.join(config.root, 'resources', 'sound'),
})
