import sys
import os.path
import configparser

import requests
from bs4 import BeautifulSoup


AUTH = 'https://auth.fit.cvut.cz'
EDUX = 'https://edux.fit.cvut.cz'


def auth(target, auth_file='./auth.cfg'):
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
        sys.exit(1)

    if target == 'oauth':
        return username, password, callback
    else:
        return username, password


def session_edux(username, password):
    url = EDUX + '/start?do=login'
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


def session_api(username, password):
    url = AUTH + '/oauth/oauth/token'
    session = requests.Session()

    data = {
        'client_id': username,
        'client_secret': password,
        'grant_type': 'client_credentials',
    }

    r = session.post(url, data=data)
    try:
        r.raise_for_status()
    except:
        # TODO bad auth
        raise

    response = r.json()
    session.headers['Authorization'] = 'Bearer {}'.format(response['access_token'])
    expiration = datetime.datetime.now() + datetime.timedelta(seconds=response['expires_in'] - 60)
    # only needed for one-time checks
    # (enrolled courses, usermap usernames)
    # thus, no need to check expiration

    return session
