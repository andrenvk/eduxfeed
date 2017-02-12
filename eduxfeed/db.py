import os
import re
import pickle
import configparser


DB_DIR = os.path.realpath(os.environ.get('DB_DIR', './db'))

BASE = {
    'edux': os.path.join(DB_DIR, 'edux'),
    'user': os.path.join(DB_DIR, 'user'),
}
EXT = '.txt'
USER = {
    'config': '' + EXT,
    'feed': '_feed.p',
}
EDUX = {
    'pages': 'edux' + EXT,
    'media': 'edux_media_{}' + EXT,
    'authors': 'authors' + EXT,
}
OPEN = {
    # encoding must be set
    'encoding': 'utf-8',
    'newline': '\n',
}


def _configparser(case_sensitive=True):
    """Configparser with default case-sensitivity"""
    config = configparser.ConfigParser()
    if case_sensitive:
        config.optionxform = str
    return config


def _getter(path):
    """Loads configparser config"""
    config = _configparser()
    # ok if config file does not exist
    config.read(path, encoding=OPEN['encoding'])

    # return dict(config.items())
    # behaves like dict
    return config


def _setter(path, config):
    """Saves configparser config"""
    with open(path, mode='w', **OPEN) as f:
        config.write(f)


def init():
    """Initializes db directories"""
    for path in BASE.values():
        if not os.path.exists(path):
            os.makedirs(path)


def edux_path():
    """Path to EDUX config"""
    return os.path.join(BASE['edux'], EDUX['pages'])


def edux_pages():
    """Loads EDUX pages"""
    return _getter(edux_path())


def edux_pages_set(config):
    """Saves EDUX pages"""
    _setter(edux_path(), config)


def edux_media(course):
    """Loads EDUX media"""
    path = os.path.join(BASE['edux'], EDUX['media'])
    return _getter(path.format(course))


def edux_media_set(course, config):
    """Saves EDUX media"""
    path = os.path.join(BASE['edux'], EDUX['media'])
    _setter(path.format(course), config)


def edux_authors():
    """Loads EDUX authors"""
    path = os.path.join(BASE['edux'], EDUX['authors'])
    return _getter(path)


def edux_authors_set(config):
    """Saves EDUX authors"""
    path = os.path.join(BASE['edux'], EDUX['authors'])
    _setter(path, config)


def user_base(username):
    """Base path of user files"""
    return os.path.join(BASE['user'], username)


def user_path(username):
    """Path to user config"""
    return user_base(username) + USER['config']


def user_exist(username):
    """Whether user exists"""
    return os.path.exists(user_path(username))


def user_list():
    """List of registered users"""
    files = [f for f in os.listdir(BASE['user']) if os.path.isfile(os.path.join(BASE['user'], f))]
    # accept just <username>.txt, ignore .dotfiles and user-specific files like <username>_feed.p
    users = [f.split(EXT)[0] for f in files if not (re.search('_', f) or re.match('\.', f))]
    users = [u for u in users if re.match('^[a-z0-9]$', u)]

    return users


def user_config(username):
    """Loads user config"""
    return _getter(user_path(username))


def user_config_set(username, config):
    """Saves user config"""
    _setter(user_path(username), config)


def user_feed(username):
    """Loads user feed"""
    path = user_base(username) + USER['feed']
    with open(path, 'rb') as f:
        feed = pickle.load(f)
    # except FileNotFoundError
    # no need -- created upon register

    return feed


def user_feed_set(username, feed):
    """Saves user feed"""
    path = user_base(username) + USER['feed']
    with open(path, 'wb') as f:
        pickle.dump(feed, f, pickle.HIGHEST_PROTOCOL)
