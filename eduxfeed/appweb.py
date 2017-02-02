from .db import user_feed
from .appcode import user_login, user_key
from .appcode import item_hash, item_markread
from .auth import AUTH, EDUX
from .auth import auth

import re

import requests
from flask import Flask, render_template, url_for, request, redirect, abort


app = Flask(__name__)


@app.route('/')
def index():
    return render_template('oauth.html', url=url_for('oauth'))


@app.route('/authorize/redirect')
def oauth():
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
        return redirect(url_for('index'))

    user_login(username)
    return redirect(url_for('settings', username=username, key=user_key(username)))


@app.route('/app/<username>')
def settings(username):
    query = request.args.to_dict()
    if not user_exist(username):
        abort(404)
    elif ('key' not in query or query['key'] != user_key(username)):
        return redirect(url_for('index'))

    return 'OK'


@app.route('/app/<username>/feed.xml')
def feed(username):
    query = request.args.to_dict()
    if not user_exist(username):
        abort(404)
    elif ('key' not in query or query['key'] != user_key(username)):
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

    items.sort(key=lambda item: item['item']['to'], reverse=True)
    return render_template('feed.xml', username=username, items=items)


@app.route('/app/<username>/redirect')
def redirect():
    query = request.args.to_dict()
    if not user_exist(username):
        abort(404)
    args = ['src', 'code', 'path', 'from', 'to', 'hash']
    for arg in args:
        if arg not in query:
            return redirect(url_for('index'))

    digest = item_hash(username, args=(args['src'], args['code'], args['path'], args['from'], args['to']))
    if digest != args['hash']:
        return redirect(url_for('index'))

    if args['src'] == 'pages':
        url = EDUX + '/courses/' + args['path'] + '/start'

        diff = True
        if 'target' in args and args['target'] == 'current':
            diff = False
        if diff:
            url = url + '?do=diff&rev2[]={}&rev2[]={}'
            url = url.format(args['from'], args['to'])

    elif args['src'] == 'media':
        diff = False
        url = EDUX + '/courses/' + args['path']

    item_markread(username, query, diff)
    return redirect(url)


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
