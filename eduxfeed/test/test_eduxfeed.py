from eduxfeed.auth import EDUX
from eduxfeed import appweb
from eduxfeed import auth

import os
import re
import requests
from bs4 import BeautifulSoup

import pytest


AUTH = 'eduxfeed/test/fixtures/auth.cfg.sample'


@pytest.mark.parametrize(
    ['target', 'file'],
    [(target, AUTH) for target in ('edux', 'api', 'oauth')],
)
def test_config(target, file):
    credentials = auth.auth(target, file)
    assert len(credentials) == 2 if target != 'oauth' else 3


def test_config_fail():
    with pytest.raises(KeyError):
        auth.auth('non-existent-section', AUTH)


@pytest.mark.parametrize(
    ['files', 'valid'],
    [
        (('.dotfile', '_file', 'also_file', 'file_'), 0),
        (('dotfile.', 'normal.txt'), 2),
    ],
)
def test_db(files, valid):
    # test user_list
    users = [f.split('.')[0] for f in files if not (re.search('_', f) or re.match('\.', f))]
    assert len(users) == valid


@pytest.mark.parametrize(
    ['path', 'output'],
    [
        ('MI-PYT/x/y/z', 'x/y/z'),
        ('MI-PYT/x/y/z/', 'x/y/z'),
        ('MI-PYT/lectures/start', 'lectures'),
        ('MI-PYT/lectures', 'lectures'),
        ('MI-PYT/start', 'MI-PYT'),
        ('MI-PYT/', 'MI-PYT'),
        ('MI-PYT', 'MI-PYT'),
        ('MI-PYT/_media/en/file', 'en/file'),
        ('MI-PYT/_media/file.txt', 'file.txt'),
        # should not happen, should start w/ code
        ('/_media/file.txt', '/_media/file.txt'),
    ],
)
def test_filter_path(path, output):
    f = appweb.filter_path
    assert f(path) == output


ITEM = {
    'src': 'SRC',
    'code': 'CODE',
    'path': 'PATH',
    'item': {
        'from': 123,
        'to': 321,
        'hash': 'HASH',
    }
}
@pytest.mark.parametrize(
    ['target', 'escape'],
    [(t, e) for t in ('TARGET', None) for e in (True, False)],
)
def _test_filter_link(target, escape):
    f = appweb.filter_link
    link = str(f(ITEM, 'USERNAME', target, escape))
    assert re.match('http', link)
    # assert len(link.split('?')) == 2
    path, query = link.split('?')
    # assertion based on current logic
    assert re.search('USERNAME', path)
    assert '&' in query
    if escape:
        assert re.search('&[a-z]+;')
    if target:
        assert re.search('target={}$'.format(target))
    for k, v in ITEM.items():
        if type(v) is not dict:
            assert '{}={}'.format(k, v) in query
        else:
            for kk, vv in v.items():
                assert '{}={}'.format(kk, vv) in query


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
        try:
            for course in feed['pages']:
                for path in feed['pages'][course]:
                    if re.match('[^/]+/en/', path):
                        del feed['pages'][course][path]
                if not feed['pages'][course]:
                    del feed['pages'][course]
            if not feed['pages']:
                del feed['pages']

            for course in feed['media']:
                for path in feed['media'][course]:
                    if re.match('[^/]+/_media/en/', path):
                        del feed['media'][course][path]
            if not feed['media'][course]:
                    del feed['media'][course]
            if not feed['media']:
                del feed['media']
        except:
            pass

    # deleted courses
    for course in user['COURSES']:
        if course not in courses:
            del user['COURSES'][course]
            try:
                del feed['pages'][course]
                del feed['media'][course]
            except:
                pass

    # added courses
    courses_all = db.edux_pages()['COURSES']
    for course in courses:
        if course not in user['COURSES']:
            user['COURSES'][course] = courses_all[course]

    db.user_feed_set(username, feed)
    db.user_config_set(username, user)


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

        digest = item_hash(username, args=(item['src'], item['code'], item['path'], path['from'], path['to']))
        path['hash'] = digest

    db.user_feed_set(username, feed)


def edux_check_pages(course, session, authors, timestamp):
    try:
        r = session.get(FEED.format(course=course), params=FEED_PARAMS)
        r.raise_for_status()
    except:
        return None

    last = edux_feed_last(r.text)
    if timestamp is None:
        # init only
        return last
    if not last > timestamp:
        return None

    items = {}
    parser = BeautifulSoup(r.text, 'html.parser')
    entries = parser.find_all('entry')
    for entry in entries:
        # sorted from newest (thus, highest timestamp)
        # https://www.dokuwiki.org/syndication#item_sorting
        link = entry.link['href']
        rev = int(re.search('\?.*rev=(\d+)', link).group(1))
        if not rev > timestamp:
            break
        link = re.sub('^.*?/courses/', EDUX + '/courses/', link)
        path = re.sub('^.*?/courses/', '', link)
        path = re.sub('\?.*$', '', path)
        # course code has to be present
        # e.g. PDD.16 redirects to PDD, thus different code and start of path
        if re.match('[^/]+/classification/student/', path) or re.match('[^/]+/student/', path):
            continue

        items[rev] = {}
        item = items[rev]
        item['path'] = {
            'path': path,
            'link': link,
        }

        date, time = entry.published.text.split('T')
        prev = edux_page_prev(path, session, timestamp) if timestamp > 0 else rev
        item['time'] = {
            'date': date,
            'time': time[:5],
            'timestamp': rev,
            'prev': prev,
        }

        username = entry.author.text.strip()
        if username not in authors:
            name = edux_author(username, session=None)
            if name:
                authors[username] = {}
                # preserve order in case of config
                authors[username]['first'] = name['first']
                authors[username]['last'] = name['last']

        if username not in authors:
            item['author'] = {
                'username': username,
            }
        else:
            item['author'] = {
                'username': username,
                'first': authors[username]['first'],
                'last': authors[username]['last'],
            }

    return items


def edux_check_media(course, session):
    items = {}
    media = db.edux_media(course)
    ajax = AJAX.format(course=course)

    # possible redirect on POST
    # e.g. BI-3DT.1 => BI-3DT
    r = session.get(ajax)
    ajax = r.request.url

    namespaces = ['']
    d = deque(namespaces)
    data = {'call': 'medians'}
    while len(d):
        data['ns'] = d.popleft()
        try:
            r = session.post(ajax, data=data)
            r.raise_for_status()
        except:
            # e.g. non-existent course MI-SPI-1
            continue
        parser = BeautifulSoup(r.text, 'html.parser')
        for a in parser.find_all('a'):
            ns = a['href'].split('=')[-1]
            # re.search('mailto', ns) if error passed
            namespaces.append(ns)
            d.append(ns)

    data = {'call': 'medialist'}
    for ns in namespaces:
        data['ns'] = ns
        r = session.post(ajax, data=data)
        parser = BeautifulSoup(r.text, 'html.parser')
        for div in parser.find_all('div', {'class': ['even', 'odd']}):
            link = div.find(lambda tag: tag.name == 'a' and tag.has_attr('href'))['href']
            # link to full -- compatibility with pages
            link = re.sub('^.*?/courses/', EDUX + '/courses/', link)
            path = re.sub('^.*?/courses/', '', link)
            if re.match('[^/]+/_media/student/', path):
                continue
            info = div.span.i
            date, time = info.text.replace('/', '-').split(' ')
            size, unit = info.next_sibling.string.strip('( )').split(' ')
            timestamp = int(datetime.strptime('{} {}'.format(date, time), '%Y-%m-%d %H:%M').timestamp())
            if path not in media[course] or int(media[course][path]) < timestamp:
                items[path] = {
                    'path': {
                        'path': path,
                        'link': link,
                    },
                    'time': {
                        'date': date,
                        'time': time,
                        'timestamp': timestamp,
                    },
                    'info': {
                        'size': size,
                        'unit': unit,
                        'new': path not in media[course],
                    },
                }
                media[course][path] = str(timestamp)

    db.edux_media_set(course, media)
    return items


def edux_page_prev(path, session, timestamp):
    url = '{edux}/courses/{path}?do=revisions'
    try:
        r = session.get(url.format(edux=EDUX, path=path))
        r.raise_for_status()
    except:
        # need to return actual timestamp
        # behaves as a newly created page
        return int(timestamp)

    prev = int(timestamp)
    parser = BeautifulSoup(r.text, 'html.parser')
    for revision in parser.find_all('input', {'name': 'rev2[]'}):
        # last revision named 'current'
        try:
            rev = int(revision['value'])
            if rev <= prev:
                prev = rev
                break
        except:
            continue

    return prev


def edux_feed_last(feed):
    parser = BeautifulSoup(feed, 'html.parser')
    try:
        # sorted from newest
        # https://www.dokuwiki.org/syndication#item_sorting
        link = parser.entry.link['href']
        rev = re.search('\?.*rev=(\d+)', link).group(1)
        return int(rev)
    except:
        return 0

