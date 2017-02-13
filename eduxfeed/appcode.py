from . import db
from .api import user_enrolled

import re
import uuid
import hashlib


def user_key(username):
    """
    Returns user auth key, used to access feed and user settings

    Args:
        username (str): registered user

    Returns:
        key (str): user key
    """
    config = db.user_config(username)
    return config['CONFIG']['key']


def user_secret(username):
    """
    Returns user secret, used to create user key and hash digests

    Args:
        username (str): registered user

    Returns:
        secret (str): user secret
    """
    config = db.user_config(username)
    return config['CONFIG']['secret']


def user_login(username):
    """
    Logs in user (register user if not yet)

    Args:
        username (str): CTU username
    """
    if not db.user_exist(username):
        user_register(username)


def user_register(username):
    """
    Register new user

    Creates user config file
    - secret and key
    - feed settings
    - courses to check

    Args:
        username (str): CTU username
    """
    config = db.user_config(username)

    config['CONFIG'] = {}
    cfg = config['CONFIG']
    secret = str(uuid.uuid4())
    cfg['secret'] = secret
    cfg['key'] = item_hash(username, args=[], secret=secret)

    config['FEED'] = {}
    cfg = config['FEED']
    cfg['media'] = str(int(True))
    cfg['en'] = str(int(False))

    config['COURSES'] = {}
    cfg = config['COURSES']
    courses = user_enrolled(username, session=None)
    courses_all = db.edux_pages()['COURSES']
    for course in courses:
        if course in courses_all:
            cfg[course] = courses_all[course]

    db.user_config_set(username, config)
    db.user_feed_set(username, feed={})


def user_settings(username):
    """
    Returns user settings

    Args:
        username (str): registered user

    Returns:
        user settings (tuple):

        config (dict): feed settings read from user config file

        courses (list): list of followed courses (courses to be checked for changes)
        courses_all (list): list of all available courses (for option to follow a new course)
    """
    user = db.user_config(username)

    config = {}
    config['media'] = user['FEED'].getboolean('media', fallback=True)
    config['en'] = user['FEED'].getboolean('en', fallback=False)

    courses = list(user['COURSES'])
    courses_all = list(db.edux_pages()['COURSES'])

    return config, courses, courses_all


def user_update(username, config, courses):
    """
    Updates user settings

    Based on a call to settings update endpoint,
    config contains list of checked options of feed settings,
    courses contain list of checked courses to follow.
    User settings and resulting feed get updated accordingly.

    Args:
        username (str): registered user
        config (list): feed settings update object
        courses (list): followed courses update object
    """
    user = db.user_config(username)
    feed = db.user_feed(username)

    if 'media' in config:
        user['FEED']['media'] = str(int(True))
    elif user['FEED'].getboolean('media', fallback=True):
        # 'media' disabled
        user['FEED']['media'] = str(int(False))
        try:
            del feed['media']
        except:
            pass

    if 'en' in config:
        user['FEED']['en'] = str(int(True))
    elif user['FEED'].getboolean('en', fallback=False):
        # 'en' disabled
        user['FEED']['en'] = str(int(False))
        for src in ('pages', 'media'):
            if src in feed:
                delete = {}
                for course in feed[src]:
                    delete[course] = []
                    for path in feed[src][course]:
                        if re.match('[^/]+/(_media/)?en/', path):
                            delete[course].append(path)
                for course in delete:
                    for key in delete[course]:
                        del feed[src][course][key]
                    if not feed[src][course]:
                        del feed[src][course]

    # deleted courses
    for course in user['COURSES']:
        if course not in courses:
            del user['COURSES'][course]
            for src in ('pages', 'media'):
                if src in feed and course in feed[src]:
                    del feed[src][course]

    for src in ('pages', 'media'):
        if src in feed and not feed[src]:
            del feed[src]

    # added courses
    courses_all = db.edux_pages()['COURSES']
    for course in courses:
        if course not in user['COURSES']:
            user['COURSES'][course] = courses_all[course]

    db.user_feed_set(username, feed)
    db.user_config_set(username, user)


def item_hash(username, args, secret=None):
    """
    Computes cummulative hash of args

    Returns hash digest based on succesive updates of hash,
    args applied in order, must support string cast,
    secret is applied in the end.

    Args:
        username (str): registered user
        args (iterable): args to be applied, usually list of strings
        secret (str): last arg to be applied to hash (defaults to user secret)

    Returns:
        hash (str): computed hash digest
    """
    if not secret:
        secret = user_secret(username)

    h = hashlib.sha256()
    for arg in args:
        h.update(str(arg).encode('ascii'))
    h.update(secret.encode('ascii'))

    return h.hexdigest()


def item_markread(username, item, diff):
    """
    Processes feed item markes as read

    Updates user feed accordingly. All info needed is contained in item.
    Removes item from feed. In case of already updated item in the feed
    (thus, processing of an old item), it is possible to selectively
    update the feed item, removing only info bound to this item being processed.

    Args:
        username (str): registered user
        item (dict): contains feed item link info (src, code, path, from, to)
        diff (bool): check for remains of a feed item (diff=True) or remove completely
    """
    feed = db.user_feed(username)

    try:
        src = feed[item['src']]
        code = src[item['code']]
        path = code[item['path']]
    except:
        # already deleted from feed
        return

    to = int(item['to'])
    if to == path['to'] or not diff:
        # remove item completely
        # possible cascade delete
        del code[item['path']]
        if not code:
            del src[item['code']]
        if not src:
            del feed[item['src']]
    else:
        # feed has new updates
        delete = []
        for timestamp in path['updates']:
            if not timestamp > to:
                delete.append(timestamp)
        for key in delete:
            del path['updates'][key]
        if path['from'] < to:
            path['from'] = to
            digest = item_hash(username, args=(item['src'], item['code'], item['path'], path['from'], path['to']))
            path['hash'] = digest

    db.user_feed_set(username, feed)
