from .db import user_exist, user_feed
from .appcode import user_login, user_key, user_settings, user_update
from .appcode import item_hash, item_markread
from .auth import AUTH, EDUX
from .auth import auth

import re
from datetime import datetime

import requests
from flask import Flask, render_template, url_for, request, redirect, abort


app = Flask(__name__)


@app.route('/')
def index():
    """Web app, home route, displays login screen"""
    return render_template('oauth.html', url=url_for('oauth'))


@app.route('/authorize/redirect')
def oauth():
    """Web app, login 1st step, redirects to auth server"""
    username, _, callback = auth(target='oauth')
    url = AUTH + '/oauth/authorize'
    params = {
        'client_id': username,
        'response_type': 'code',
        'redirect_uri': callback,
    }
    req = requests.Request('GET', url, params=params)
    return redirect(req.prepare().url)


@app.route('/authorize')
def authorize():
    """Web app, login 2nd step, auth server callbacks the app"""
    query = request.args.to_dict()
    if 'code' not in query:
        return redirect(url_for('index'))

    username, password, callback = auth(target='oauth')
    url = AUTH + '/oauth/oauth/token'
    data = {
        'code': query['code'],
        'client_id': username,
        'client_secret': password,
        'redirect_uri': callback,
        'grant_type': 'authorization_code',
    }

    try:
        r = requests.post(url, data=data)
        r.raise_for_status()
        token = r.json()['access_token']
        token_info = AUTH + '/oauth/check_token'
        r = requests.get(token_info, params={'token': token})
        r.raise_for_status()
        username = r.json()['user_name']
    except:
        # login disabled if problems with auth
        return redirect(url_for('index'))

    user_login(username)
    return redirect(url_for('settings', username=username, key=user_key(username)))


@app.route('/app/<username>')
def settings(username):
    """Web app, user settings, key required in url"""
    query = request.args.to_dict()
    if not user_exist(username):
        abort(400)
    elif ('key' not in query or query['key'] != user_key(username)):
        abort(400)

    config, courses, courses_all = user_settings(username)

    return render_template(
        'settings.html',
        feed=url_for('feed', username=username, key=user_key(username)),
        endpoint=url_for('update', username=username),
        courses_all=courses_all,
        courses=courses,
        config=config,
    )


@app.route('/app/<username>/update', methods=['POST'])
def update(username):
    """Web app, user settings endpoint, settings updated upon call"""
    if not user_exist(username):
        abort(400)

    formdata = dict(zip(request.form.keys(), request.form.listvalues()))
    if ('key' not in formdata or formdata['key'][0] != user_key(username)):
        abort(400)

    config, courses = [], []
    if 'config' in formdata:
        config = formdata['config']
    if 'course' in formdata:
        courses = formdata['course']

    user_update(username, config, courses)
    return 'OK', 200


@app.route('/app/<username>/feed.xml')
def feed(username):
    """Web app, feed output, atom format"""
    query = request.args.to_dict()
    if not user_exist(username):
        abort(400)
    elif ('key' not in query or query['key'] != user_key(username)):
        # actually exposing info about registered users
        # but could be more useful to know what is wrong
        return render_template('feed_unauthorized.xml')

    items = []
    feed = user_feed(username)

    for src in feed:
        for code in feed[src]:
            for path in feed[src][code]:
                items.append({
                    'src': src,
                    'code': code,
                    'path': path,
                    'item': feed[src][code][path],
                })

    headers = {'Content-Type': 'application/xml'}
    items.sort(key=lambda item: item['item']['to'], reverse=True)
    return render_template('feed.xml', username=username, items=items), 200, headers


@app.route('/app/<username>/read')
def read(username):
    """Web app, read feed item, gets processed and redirects to EDUX"""
    query = request.args.to_dict()
    if not user_exist(username):
        abort(400)
    args = ['src', 'code', 'path', 'from', 'to', 'hash']
    for arg in args:
        if arg not in query:
            abort(400)

    digest = item_hash(username, args=(query['src'], query['code'], query['path'], query['from'], query['to']))
    if digest != query['hash']:
        return redirect(url_for('index'))

    url = EDUX + '/courses/' + query['path']
    if query['src'] == 'media':
        diff = False
    elif query['src'] == 'pages':
        diff = True
        if 'target' in query and query['target'] == 'current':
            diff = False
        if diff:
            url = url + '?do=diff&rev2[]={}&rev2[]={}'
            url = url.format(query['from'], query['to'])

    item_markread(username, query, diff)
    return redirect(url)


@app.template_filter('path')
def filter_path(path):
    """Web app, feed template, path filter"""
    path = re.sub('/(start)?$', '', path)
    path = re.sub('^[^/]+(/_media)?/', '', path)
    # if root namespace, then 'code' remains:
    # MI-PYT/lectures/start => lectures
    # MI-PYT/lectures => lectures
    # MI-PYT/start => MI-PYT
    # MI-PYT/ => MI=PYT
    # MI-PYT => MI-PYT

    return path


@app.template_filter('updated')
def filter_updated(timestamp):
    """Web app, feed template, time in xsd:dateTime format"""
    return datetime.fromtimestamp(int(timestamp)).strftime('%Y-%m-%dT%H:%M:%S')


@app.template_filter('uniq')
def filter_uniq(item):
    """Web app, feed template, creates unique item id"""
    detail = item['item']
    args = (item['code'], item['path'], str(detail['from']), str(detail['to']))

    return ':'.join(args)


@app.template_filter('author')
def filter_author(detail):
    """Web app, feed template, additional info: author"""
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
    """Web app, feed template, additional info: time"""
    time = detail['time']
    datetime = '{} {}'.format(time['date'], time['time'])

    return datetime


@app.template_filter('size')
def filter_size(detail):
    """Web app, feed template, additional info: (file) size"""
    info = detail['info']
    size = '{} {}'.format(info['size'], info['unit'])

    return size


@app.template_filter('sort')
def filter_sort(details):
    """Web app, feed template, sort edits in history"""
    return sorted(details)


@app.template_filter('link')
def filter_link(item, username, target=None, escape=True):
    """Web app, feed template, creates item link (to be later processed by the app)"""
    params = [
        # preserve order
        ('src', item['src']),
        ('code', item['code']),
        ('path', item['path']),
        ('from', str(item['item']['from'])),
        ('to', str(item['item']['to'])),
        ('hash', item['item']['hash']),
    ]
    if target:
        params.append(('target', target))

    # requests performs url encoding, '/' => %2F
    # create url manually, http://stackoverflow.com/a/23497903
    # req = requests.Request('GET', url_for('read', username=username, _external=True), params=params)
    # return req.prepare().url

    # '&' apperently breaks feed
    amp = '&amp;' if escape else '&'
    params = amp.join(['='.join(param) for param in params])
    url = url_for('read', username=username, _external=True)
    return '{}?{}'.format(url, params)
