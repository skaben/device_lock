import os.path as op
from skabenclient.config import Config

config = Config(op.join('conf', 'config.yml'))
config.update({
    'sound_dir': op.join(config.root, 'resources', 'sound'),
})
