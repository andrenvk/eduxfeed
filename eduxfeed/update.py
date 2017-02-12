from . import db
from .auth import EDUX
from .auth import session_edux
from .appcode import item_hash
from .api import edux_author

import re
from datetime import datetime
from collections import deque

import requests
from bs4 import BeautifulSoup


AJAX = EDUX + '/courses/{course}/lib/exe/ajax.php'
FEED = EDUX + '/courses/{course}/feed.php'
FEED_PARAMS = {
    'mode': 'recent',
    'view': 'pages',
    'type': 'atom1',
    'content': 'abstract',
    'linkto': 'page',
    'minor': '1',
}


def update():
    session = session_edux()
    changes = edux_check(session)
    pages = db.edux_pages()
    courses = pages['COURSES']
    users = db.user_list()
    for username in users:
        feed = db.user_feed(username)
        config = db.user_config(username)
        en = config['FEED'].getboolean('en', fallback=False)
        for src in changes:
            if not config['FEED'].getboolean(src, fallback=True):
                continue
            for code in config['COURSES']:
                if code not in changes[src]:
                    continue
                if src not in feed:
                    feed[src] = {}
                if code not in feed[src]:
                    feed[src][code] = {}
                content = feed[src][code]
                updates = changes[src][code]

                for update in updates.values():
                    path = update['path']['path']
                    if not en and re.match('[^/]+(/_media)?/en/', path):
                        continue
                    if path not in content:
                        content[path] = {}
                        content[path]['updates'] = {}

                    content[path]['new'] = False
                    timestamp = update['time']['timestamp']
                    if 'from' not in content[path]:
                        if src == 'pages':
                            prev = update['time']['prev']
                            if prev == timestamp:
                                content[path]['new'] = True
                            content[path]['from'] = prev
                        elif src == 'media':
                            content[path]['from'] = timestamp
                            content[path]['new'] = update['info']['new']
                    content[path]['to'] = timestamp

                    digest = item_hash(username, args=(src, code, path, content[path]['from'], content[path]['to']))
                    content[path]['hash'] = digest
                    content[path]['updates'][timestamp] = {
                        'time': update['time'],
                        'info': update['author'] if src == 'pages' else update['info'],
                    }

        for course in config['COURSES']:
            config['COURSES'][course] = courses[course]
        db.user_config_set(username, config)
        db.user_feed_set(username, feed)


def edux_check(session):
    changes = {
        'pages': {},
        'media': {},
    }
    edux = db.edux_pages()
    courses = edux['COURSES']
    authors = db.edux_authors()

    for course in courses:
        print('PAGES', course)
        pages = edux_check_pages(course, session, authors, timestamp=int(courses[course]))
        if pages:
            changes['pages'][course] = pages
            courses[course] = str(max(pages))
        print('MEDIA', course)
        media = edux_check_media(course, session)
        if media:
            changes['media'][course] = media

    db.edux_authors_set(authors)
    db.edux_pages_set(edux)
    return changes


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
        rev = int(re.search('\?(.+&)?rev=(\d+)', link).group(2))
        if not rev > timestamp:
            break
        link = re.sub('^.*?/courses/', EDUX + '/courses/', link)
        path = re.sub('^.*?/courses/', '', link)
        path = re.sub('\?.*$', '', path)
        # course code has to be present
        # e.g. PDD.16 redirects to PDD, thus different code and start of path
        if (re.match('[^/]+/classification/(en/)?student/', path) or
            re.match('[^/]+/classification/view/', path) or
            re.match('[^/]+/(en/)?student/', path)):
            # PEP 8 inconclusive about this indent
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
            if re.match('[^/]+/_media/(en/)?student/', path):
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
        rev = re.search('\?(.+&)?rev=(\d+)', link).group(2)
        return int(rev)
    except:
        return 0
