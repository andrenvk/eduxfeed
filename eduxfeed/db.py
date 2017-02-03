import os
import re
import pickle
import configparser


EXT = '.txt'
DIR = os.path.dirname(os.path.realpath(__file__))
BASE = {
    'edux': os.path.join(DIR, 'edux'),
    'user': os.path.join(DIR, 'user'),
}
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
    'encoding': 'utf-8',
    'newline': '\n',
}


def _configparser(case_sensitive=True):
    config = configparser.ConfigParser()
    if case_sensitive:
        config.optionxform = str
    return config


def _getter(path):
    config = _configparser()
    # ok if config file does not exist
    config.read(path)

    # return dict(config.items())
    # behaves like dict
    return config


def _setter(path, config):
    with open(path, mode='w', **OPEN) as f:
        config.write(f)


def init():
    for path in BASE.values():
        if not os.path.exists(path):
            os.makedirs(path)


def edux_path():
    return os.path.join(BASE['edux'], EDUX['pages'])


def edux_pages():
    return _getter(edux_path())


def edux_pages_set(config):
    _setter(edux_path(), config)


def edux_media(course):
    path = os.path.join(BASE['edux'], EDUX['media'])
    return _getter(path.format(course))


def edux_media_set(course, config):
    path = os.path.join(BASE['edux'], EDUX['media'])
    _setter(path.format(course), config)


def edux_authors():
    path = os.path.join(BASE['edux'], EDUX['authors'])
    return _getter(path)


def edux_authors_set(config):
    path = os.path.join(BASE['edux'], EDUX['authors'])
    _setter(path, config)


def user_base(username):
    return os.path.join(BASE['user'], username)


def user_path(username):
    return user_base(username) + USER['config']


def user_exist(username):
    return os.path.exists(user_path(username))


def user_list():
    files = [f for f in os.listdir(BASE['user']) if os.path.isfile(f)]
    # accept just <username>.txt, ignore .dotfiles and user-specific files like <username>_feed.p
    users = [f.split(EXT)[0] for f in files if not (re.search('_', f) or re.match('\.', f))]

    return users


def user_config(username):
    return _getter(user_path(username))


def user_config_set(username, config):
    _setter(user_path(username), config)


def user_feed(username):
    path = user_base(username) + USER['feed']
    with open(path, 'rb') as f:
        feed = pickle.load(f)
    # except FileNotFoundError
    # no need -- created upon register

    return feed


def user_feed_set(username, feed):
    path = user_base(username) + USER['feed']
    with open(path, 'wb') as f:
        pickle.dump(feed, f, pickle.HIGHEST_PROTOCOL)
