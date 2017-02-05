import os
import configparser
# from datetime import datetime

import requests
from bs4 import BeautifulSoup


AUTH_FILE = os.path.realpath(os.environ.get('AUTH_FILE', './auth.cfg'))

AUTH = 'https://auth.fit.cvut.cz'
EDUX = 'https://edux.fit.cvut.cz'


def auth(target=None, file=None):
    if file is None:
        file = AUTH_FILE
    if target is None:
        return os.path.isfile(file)

    credentials = []
    config = configparser.ConfigParser()
    try:
        config.read(file)
        credentials.append(config[target]['username'])
        credentials.append(config[target]['password'])
        if target == 'oauth':
            credentials.append(config[target]['callback'])
    except:
        print('Config file error.')
        with open(os.path.join(os.path.dirname(__file__), 'auth.cfg.sample')) as f:
            print('Make sure the credentials are valid.')
            print('See below sample contents of auth.cfg:')
            print(f.read())
        # raising exception because file was set ok, but is missing auth info
        # it is not clear in advance which auth sections will be used
        # (could be only init and update -- the main logic)
        # (also bad credentials -- oauth can't be dry-run)
        # thus no check performed upon start a raise now
        raise

    return credentials


def session_edux(username=None, password=None):
    if username is None or password is None:
        username, password = auth(target='edux')
    url = EDUX + '/start?do=login'
    session = requests.Session()

    def get_formdata(html):
        formdata = {}
        parser = BeautifulSoup(html, 'html.parser')
        form = parser.find('form', {'method': 'post'})
        for inp in form.find_all('input'):
            if inp['type'] != 'submit' and 'value' in inp.attrs:
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
        # this is heavily dependent on the structure of the web
        # works as of now, can change in future, check in tests
        # however, the app's logic allows non-auth edux session
        # it just won't produce any updates until it works again
        pass

    return session


def session_api(username=None, password=None):
    if username is None or password is None:
        username, password = auth(target='api')
    url = AUTH + '/oauth/oauth/token'
    session = requests.Session()

    data = {
        'client_id': username,
        'client_secret': password,
        'grant_type': 'client_credentials',
    }

    try:
        r = session.post(url, data=data)
        r.raise_for_status()
        response = r.json()
        session.headers['Authorization'] = 'Bearer {}'.format(response['access_token'])
        # expiration = datetime.now() + datetime.timedelta(seconds=response['expires_in'] - 60)
        # only needed for one-time checks
        # (enrolled courses, usermap usernames)
        # thus, no need to check expiration
        # otherwise import datetime
    except:
        # can fail because of bad credentials (or api provider problem)
        # none of this is a fault of this app
        # in such case the app flow continues
        # but no courses are automatically subscribed
        pass

    return session
