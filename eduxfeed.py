import os
import re
import sys
import datetime
import configparser
import hashlib
import uuid

# import lxml
import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template, url_for, request, redirect, abort

KOSAPI = 'https://kosapi.fit.cvut.cz/api/3'
EDUX = 'https://edux.fit.cvut.cz'
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

    key = user_key(username)
    return redirect(url_for('settings', username=username, key=key))


def user_path(username):
    return os.path.join(DIR, USERDATA, username + '.txt')


def user_exist(username):
    return os.path.exists(user_path(username))


def user_key(username):
    path = user_path(username)
    config = configparser_case()

    if not user_exist(username):
        user_register(username)
    config.read(path)

    return config['AUTH']['key']


def user_register(username):
    path = user_path(username)
    config = configparser_case()

    config['AUTH'] = {}
    secret = str(uuid.uuid4())
    h = hashlib.sha256()
    h.update(secret.encode('ascii'))
    key = h.hexdigest()
    config['AUTH']['secret'] = secret
    config['AUTH']['key'] = key

    with open(path, mode='w', encoding='utf-8') as f:
        config.write(f)


@app.route('/app/<username>')
def settings(username):
    query = request.args.to_dict()
    if not user_exist(username):
        abort(404)
    elif ('key' not in query or query['key'] != user_key(username)):
        return redirect(url_for('index'))

    return 'OK'


@app.route('/app/<username>/feed.atom')
def feed(username):
    query = request.args.to_dict()
    if not user_exist(username):
        abort(404)
    elif ('key' not in query or query['key'] != user_key(username)):
        return render_template('feed_unauthorized.xml')

    return 'OK'


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
