from . import db
from .api import user_enrolled

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
    courses = user_enrolled(username)
    courses_all = db.edux_courses()
    for course in courses:
        if course in courses_all:
            cfg[course] = courses_all[course]

    db.user_config_set(username, config)
    db.user_feed_set(username, feed={})


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
