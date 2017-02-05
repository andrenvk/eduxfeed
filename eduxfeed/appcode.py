from . import db
from .api import user_enrolled

import re
import uuid
import hashlib


def user_key(username):
    config = db.user_config(username)
    return config['CONFIG']['key']


def user_secret(username):
    config = db.user_config(username)
    return config['CONFIG']['secret']


def user_login(username):
    if not db.user_exist(username):
        user_register(username)


def user_register(username):
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
    user = db.user_config(username)

    config = {}
    config['media'] = user['FEED'].getboolean('media', fallback=True)
    config['en'] = user['FEED'].getboolean('en', fallback=False)

    courses = list(user['COURSES'])
    courses_all = list(db.edux_pages()['COURSES'])

    return config, courses, courses_all


def user_update(username, config, courses):
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
                        if re.match('[^/]+(/_media)?/en/', path):
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
    if not secret:
        secret = user_secret(username)

    h = hashlib.sha256()
    for arg in args:
        h.update(str(arg).encode('ascii'))
    h.update(secret.encode('ascii'))

    return h.hexdigest()


def item_markread(username, item, diff):
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
        for timestamp in path['updates']:
            if not timestamp > to:
                del path['updates'][timestamp]
        path['from'] = to

        h = hashlib.sha256()
        h.update(item['src'].encode('ascii'))
        h.update(item['code'].endode('ascii'))
        h.update(item['path'].encode('ascii'))
        h.update(str(path['from']).encode('ascii'))
        h.update(str(path['to']).encode('ascii'))
        h.update(user_secret(username).encode('ascii'))
        path['hash'] = h.hexdigest()

    db.user_feed_set(username, feed)
