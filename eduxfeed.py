import os
import re
import sys
import pickle
import datetime
import configparser
from collections import deque
import hashlib
import uuid

# import lxml
import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template, url_for, request, redirect, abort

KOSAPI = 'https://kosapi.fit.cvut.cz/api/3'
EDUX = 'https://edux.fit.cvut.cz'
AJAX = EDUX + '/courses/{code}/lib/exe/ajax.php'
FEED = EDUX + '/courses/{code}/feed.php'
FEED_PARAMS = {
    'mode': 'recent',
    'view': 'pages',
    'type': 'atom1',
    'content': 'diff',
    'linkto': 'page',
    'minor': '1',
}

DIR = os.path.dirname(os.path.realpath(__file__))
CONFIG = 'config'
USERDATA = 'user'

app = Flask(__name__)


def main():
    app.run(debug=True)


@app.route('/')
def index():
    return render_template('oauth.html', url=url_for('oauth'))


@app.route('/authorize')
def authorize():
    query = request.args.to_dict()
    if 'code' not in query:
        return redirect(url_for('index'))

    username, password, callback = auth(target='oauth')
    url = 'https://auth.fit.cvut.cz/oauth/oauth/token'
    params = {
        'code': query['code'],
        'client_id': username,
        'client_secret': password,
        'redirect_uri': callback,
        'grant_type': 'authorization_code',
    }

    try:
        r = requests.post(url, data=params)
        r.raise_for_status()
        token = r.json()['access_token']
        token_info = 'https://auth.fit.cvut.cz/oauth/check_token'
        r = requests.get(token_info, params={'token': token})
        r.raise_for_status()
        username = r.json()['user_name']
    except:
        return redirect(url_for('index'))

    key = user_key(username)['key']
    return redirect(url_for('settings', username=username, key=key))


@app.route('/app/<username>/redirect')
def redirect():
    query = request.args.to_dict()
    if not user_exist(username):
        abort(404)
    args = ['src', 'code', 'path', 'from', 'to', 'hash']
    for arg in args:
        if arg not in query:
            return redirect(url_for('index'))

    h = hashlib.sha256()
    h.update(args['src'].encode('ascii'))
    h.update(args['code'].endode('ascii'))
    h.update(args['path'].encode('ascii'))
    h.update(args['from'].encode('ascii'))
    h.update(args['to'].encode('ascii'))
    h.update(user_key(username)['secret'].encode('ascii'))
    if args['hash'] != h.hexdigest():
        return redirect(url_for('index'))

    if args['src'] == 'pages':
        path = args['path'] if args['path'] != args['code'] else ''
        url = EDUX + '/courses/' + path + '/start'

        diff = True
        if 'target' in args and args['target'] == 'current':
            diff = False
        if diff:
            url = url + '?do=diff&rev2[]={}&rev2[]={}'
            url = url.format(args['from'], args['to'])

    elif args['src'] == 'media':
        diff = False
        url = EDUX + '/courses/' + args['path']

    app_markread(username, query, diff)
    return redirect(url)


def user_path(username):
    return os.path.join(DIR, USERDATA, username + '.txt')


def user_exist(username):
    return os.path.exists(user_path(username))


def user_key(username):
    path = user_path(username)
    config = configparser_case()

    # TODO register only after login!
    if not user_exist(username):
        user_register(username)
    config.read(path)

    keys = {
        'secret': config['CONFIG']['secret'],
        'key': config['CONFIG']['key'],
    }

    return keys


def user_register(username):
    path = user_path(username)
    config = configparser_case()
    section = 'CONFIG'

    config[section] = {}
    secret = str(uuid.uuid4())
    h = hashlib.sha256()
    h.update(secret.encode('ascii'))
    key = h.hexdigest()
    config[section]['secret'] = secret
    config[section]['key'] = key

    config[section]['media'] = str(int(True))
    config[section]['en'] = str(int(False))

    config['COURSES'] = {}
    # TODO courses

    with open(path, mode='w', encoding='utf-8') as f:
        config.write(f)


@app.route('/app/<username>')
def settings(username):
    query = request.args.to_dict()
    if not user_exist(username):
        abort(404)
    elif ('key' not in query or query['key'] != user_key(username)['key']):
        return redirect(url_for('index'))

    return 'OK'


@app.route('/app/<username>/feed.xml')
def feed(username):
    query = request.args.to_dict()
    if not user_exist(username):
        abort(404)
    elif ('key' not in query or query['key'] != user_key(username)['key']):
        return render_template('feed_unauthorized.xml')

    items = []
    feed = user_feed_get(username)
    for src in ['pages', 'media']:
        if src in feed:
            for code in feed[src]:
                for path in feed[src][code]:
                    items.append({
                        'src': src,
                        'code': code,
                        'path': path,
                        'item': feed[src][code][path],
                    })

    items.sort(key=lambda item: item['item']['to'], reverse=True)

    # TODO <updated>2017-02-01T13:38:06+01:00</updated>
    return render_template('feed.xml', username=username, items=items)


@app.template_filter('path')
def filter_path(path):
    path = re.sub('/(start)?$', '', path)
    path = re.sub('^.*?/', '', path)
    # if root namespace, then 'code' remains:
    # MI-PYT/lectures/start => lectures
    # MI-PYT/lectures => lectures
    # MI-PYT/start => MI-PYT
    # MI-PYT/ => MI=PYT
    # MI-PYT => MI-PYT

    return path


@app.template_filter('author')
def filter_author(detail):
    info = detail['info']
    if 'first' in info and 'last' in info:
        author = '{} {}'.format(info['first'], info['last'])
    elif 'username' in info:
        author = info['username']
    else:
        author = 'eduxfeed'

    return author


@app.template_filter('time')
def filter_time(detail):
    time = detail['time']
    datetime = '{} {}'.format(time['date'], time['time'])

    return datetime


@app.template_filter('size')
def filter_size(detail):
    info = detail['info']
    size = '{} {}'.format(info['size'], info['unit'])

    return size


@app.template_filter('sort')
def filter_sort(details):
    return sorted(details)


@app.template_filter('link')
def filter_link(item, username, target=None):
    # preserve order
    params = [
        ('src', item['src']),
        ('code', item['code']),
        ('path', item['path']),
        ('from', item['item']['from']),
        ('to', item['item']['to']),
        ('hash', item['item']['hash']),
    ]
    if target:
        params.append(('target', target))

    req = requests.Request('GET', url_for('redirect', username=username), params=params)
    return req.prepare().url


def auth(auth_file='./auth.cfg', target='edux', debug=True):
    config = configparser.ConfigParser()
    try:
        config.read(auth_file)
        username = config[target]['username']
        password = config[target]['password']
        if target == 'oauth':
            callback = config[target]['callback']
    except:
        print('Config file error.', file=sys.stderr)
        with open(os.path.join(os.path.dirname(__file__), 'auth.cfg.sample')) as f:
            print()
            print('See sample contents of auth.cfg:')
            print(f.read())
        if debug:
            raise
        else:
            sys.exit(1)

    if target == 'oauth':
        return username, password, callback
    else:
        return username, password


@app.route('/authorize/redirect')
def oauth():
    username, password, callback = auth(target='oauth')
    url = 'https://auth.fit.cvut.cz/oauth/authorize'
    params = {
        'client_id': username,
        'response_type': 'code',
        'redirect_uri': callback,
    }
    req = requests.Request('GET', url, params=params)
    return redirect(req.prepare().url)


def configparser_case(case_sensitive=True):
    config = configparser.ConfigParser()
    if case_sensitive:
        config.optionxform = str
    return config


def session_edux(username, password):
    url = 'https://edux.fit.cvut.cz/start?do=login'
    session = requests.Session()

    def get_formdata(html):
        formdata = {}
        parser = BeautifulSoup(html, 'html.parser')
        form = parser.find('form', {'method': 'post'})
        for inp in form.find_all('input'):
            if inp['type'] != 'submit':
                formdata[inp['name']] = inp['value']
        return formdata

    try:
        # 1] get login page
        r = session.get(url)
        r.raise_for_status()

        # 2] select local auth
        formdata = get_formdata(r.text)
        formdata['authnProvider'] = '1'
        r = session.post(url, data=formdata)
        r.raise_for_status()

        # 3] login with username and password
        formdata = get_formdata(r.text)
        formdata['u'] = username
        formdata['p'] = password
        r = session.post(url, data=formdata)
        r.raise_for_status()
    except:
        # TODO bad login does not raise exception
        # TODO debug ~ raise ~ msg
        raise

    return session


def session_kosapi(username, password):
    url = 'https://auth.fit.cvut.cz/oauth/oauth/token'
    session = requests.Session()

    formdata = {
        'client_id': username,
        'client_secret': password,
        'grant_type': 'client_credentials',
    }

    try:
        r = session.post(url, data=formdata)
        r.raise_for_status()
    except:
        # TODO bad auth
        raise

    response = r.json()
    session.headers['Authorization'] = 'Bearer {}'.format(response['access_token'])
    expiration = datetime.datetime.now() + datetime.timedelta(seconds=response['expires_in'] - 60)

    return session, expiration


def user_courses(username):
    sess = session_kosapi(*auth(target'kosapi'))
    r = sess.get(KOSAPI + '/students/{}/enrolledCourses'.format(username))
    # TODO tutorial error -- POST method error 405 Not Allowed
    # https://auth.fit.cvut.cz/manager/app-types.xhtml#service-account
    parser = BeautifulSoup(r.text, 'lxml-xml')

    courses = {}
    for course in parser.find_all('course'):
        code = re.sub('^.+/', '', course['xlink:href'].rstrip('/'))
        courses[code] = course.text

    return courses


def user_create(username, courses):
    path = os.path.join(DIR, USERDATA, username + '.txt')
    # config already exists -- user registered
    # TODO create other configs + feed
    config = configparser_case()
    config.read(path)
    last = edux_db_last(courses.keys())
    for code in courses:
        config[code] = {}
        config[code]['last'] = str(last[code])

    with open(path, mode='w', encoding='utf-8') as f:
        config.write(f)


def user_config(username):
    config = {}
    for file in [('config', ''), ('pages', '_pages'), ('media', '_media')]:
        path = os.path.join(DIR, USERDATA, username + cfg + '.txt')
        config[key] = configparser_case()
        config[key].read(path)
    return config


def user_feed_get(username):
    path = os.path.join(DIR, USERDATA, username + '_feed.p')
    # with open(path, 'wb') as f:
    #     pickle.dump(data, f, pickle.HIGHEST_PROTOCOL)
    with open('data.pickle', 'rb') as f:
        feed = pickle.load(f)

    return feed


def user_feed_set(username, feed):
    path = os.path.join(DIR, USERDATA, username + '_feed.p')
    with open(path, 'wb') as f:
        pickle.dump(feed, f, pickle.HIGHEST_PROTOCOL)


def app_update():
    users = app_users()
    changes = edux_check()
    for user in users:
        feed = user_feed_get(username)
        config = user_config(username)
        secret = config['CONFIG']['secret']
        for src in ['pages', 'media']:
            if not config['CONFIG'].getboolean(src, fallback=True):
                continue
            for code in config['COURSES']:
                if code not in changes[src]:
                    continue
                if changes[src][code]:
                    if code not in feed[src]:
                        feed[src][code] = {}
                    content = feed[src][code]
                    updates = changes[src][code]

                    for timestamp, update in updates.items():
                        path = update['path']['path']
                        if path not in content:
                            content[path] = {}

                        content[path]['new'] = False
                        timestamp = update['time']['timestamp']
                        if 'from' not in content[path]:
                            if src == 'pages':
                                old = edux_revision(path, int(changes[src][code]))
                                if old == timestamp:
                                    content[path]['new'] = True
                                content[path]['from'] = old
                            elif src == 'media':
                                content[path]['from'] = timestamp
                                content[path]['new'] = update['info']['new']
                        content[path]['to'] = timestamp

                        h = hashlib.sha256()
                        h.update(src.encode('ascii'))
                        h.update(code.endode('ascii'))
                        h.update(path.encode('ascii'))
                        h.update(str(content[path]['from']).encode('ascii'))
                        h.update(str(content[path]['to']).encode('ascii'))
                        h.update(secret.encode('ascii'))
                        content[path]['hash'] = h.hexdigest()
                        content[path]['updates'][timestamp] = {
                            'time': update['time'],
                            'info': update['author'] if src == 'pages' else update['info'],
                        }

        user_feed_set(username, feed)
        # TODO user_config_set(username, config)


def app_users():
    files = [f for f in os.listdir(os.path.join(DIR, USERDATA)) if os.path.isfile(f)]
    # accept just username.txt, ignore .dotfiles and user-specific files like username_media.txt
    users = [f.split('.')[0] for f in files if not (re.search('_', f) or re.match('\.', f))]
    return users


def app_courses():
    path = os.path.join(DIR, CONFIG, 'courses.txt')
    config = configparser_case()
    config.read(path)
    return config


def edux_check():
    changes = {}
    courses = app_courses()
    session = requests.Session() # TODO auth session
    for group in courses:
        for code in courses[group]:
            media = edux_check_media(code=code, session=session)
            pages, last = edux_check_feed(code=code, timestamp=int(courses[group][code]), session=session)
            courses[group][code] = last
            if media or pages:
                changes[code] = {
                    'pages': pages,
                    'media': media,
                }

    path = os.path.join(DIR, CONFIG, 'courses.txt')
    with open(path, mode='w', encoding='utf-8') as f:
        courses.write(f)

    return changes


def edux_check_media(code, session):
    path = os.path.join(DIR, CONFIG, 'courses_{}.txt'.format(code))
    config = configparser_case()
    config.read(path)

    ajax = AJAX.format(code=code)
    items = {}

    data = {'call': 'medians'}
    namespaces = ['']
    d = deque(namespaces)
    while len(d):
        data['ns'] = d.popleft()
        r = session.post(ajax, data=data)
        parser = BeautifulSoup(r.text, 'html.parser')
        for a in parser.find_all('a'):
            ns = a['href'].split('=')[-1]
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
            info = div.span.i
            date, time = info.text.replace('/', '-').split(' ')
            size, unit = info.next_sibling.string.strip('( )').split(' ')
            timestamp = int(datetime.datetime.strptime('{} {}'.format(date, time), '%Y-%m-%d %H:%M').timestamp())
            if path not in config[code] or int(config[code][path]) < timestamp:
                config[code][path] = str(timestamp)
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
                        'new': path not in config[code],
                    },
                }

    with open(path, mode='w', encoding='utf-8') as f:
        config.write(f)

    return items


def edux_check_feed(code, timestamp, session):
    r = session.get(FEED.format(code=code), params=FEED_PARAMS)
    try:
        r.raise_for_status()
    except:
        return None, 0

    last = edux_feed_last(r.text)
    if not last > timestamp:
        return None, 0

    items = {}
    authors = {} # TODO save authors
    session = session_kosapi(*auth(target='kosapi'))
    parser = BeautifulSoup(r.text, 'lxml-xml')
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
        if re.match('/classification/student/', path) or re.match('/student/', path):
            continue

        items[rev] = {}
        item = items[rev]
        item['path'] = {
            'path': path,
            'link': link,
        }

        date, time = entry.published.text.split('T')
        item['time'] = {
            'date': date,
            'time': time[:5],
            'timestamp': rev,
        }

        username = entry.author.name
        if username not in authors:
            names = edux_author(session, username)
            if names:
                authors[username] = {
                    'first': names[0],
                    'last': names[-1],
                }

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

    '''
    path = os.path.join(DIR, CONFIG, 'authors.txt')
    config = configparser_case()
    config.read(path)

    with open(path, mode='w', encoding='utf-8') as f:
        config.write(f)
    '''

    return items, last


def edux_author(sess, username):
    r = sess.get('https://kosapi.fit.cvut.cz/usermap/v1/people/{}'.format(username))
    try:
        r.raise_for_status()
        json = r.json()
        return (json['firstName'], json['lastName'])
    else:
        return None


def edux_courses():
    # must not be authenticated!
    url = 'https://edux.fit.cvut.cz/'
    r = requests.get(url)
    parser = BeautifulSoup(r.text, 'html.parser')

    courses = {}
    for courselist in parser.find_all('div', {'class': 'courselist_field'}):
        table = courselist.table
        if table is not None:
            for course in table.find_all('a'):
                code = course.text.strip()
                # no BIK- subjects and alike / TV course (if applicable)
                if re.match('[^-]+K-', code) or not re.search('-', code):
                    continue
                try:
                    courses[code.split('-')[0]].append(code)
                except:
                    courses[code.split('-')[0]] = [code]

    return courses


def edux_feed_last(feed):
    parser = BeautifulSoup(feed, 'lxml-xml')
    try:
        link = parser.entry.link['href']
        rev = re.search('\?.*rev=(\d+)', link).group(1)
        return int(rev)
    except:
        return 0


def edux_db_init():
    path = os.path.join(DIR, CONFIG, 'courses.txt')
    config = configparser_case()

    session = requests.Session() # TODO auth session
    courses = edux_courses()
    for group in courses:
        config[group] = {}
        for code in courses[group]:
            r = session.get(FEED.format(code=code), params=FEED_PARAMS)
            config[group][code] = str(edux_feed_last(r.text))

    with open(path, mode='w', encoding='utf-8') as f:
        config.write(f)


def edux_db_last(courses=[], file='courses.txt'):
    path = os.path.join(DIR, CONFIG, file)
    config = configparser_case()
    config.read(path)
    last = {}
    for code in courses:
        group = code.split('-')[0]
        last[code] = config[group].getint(code, fallback=0)
    return last


if __name__ == '__main__':
    main()
