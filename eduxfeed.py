import sys
import os.path
import configparser

import requests
from bs4 import BeautifulSoup


def main():
    sess = edux_session(*edux_config())
    # print(sess.get('https://edux.fit.cvut.cz/courses/BI-ZUM/feed.php').text)


def edux_config(auth_file='./auth.cfg', debug=True):
    config = configparser.ConfigParser()
    try:
        config.read(auth_file)
        username = config['edux']['username']
        password = config['edux']['password']
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
    return username, password


def edux_session(username, password):
    LOGIN = 'https://edux.fit.cvut.cz/start?do=login'
    session = requests.Session()

    def get_formdata(html):
        formdata = {}
        parser = BeautifulSoup(html, "html.parser")
        form = parser.find('form', {'method': 'post'})
        for i in form.find_all('input'):
            if i.get('type') != 'submit':
                formdata[i.get('name')] = i.get('value')
        return formdata

    try:
        # 1] get login page
        r = session.get(LOGIN)
        r.raise_for_status()

        # 2] select local auth
        formdata = get_formdata(r.text)
        formdata['authnProvider'] = '1'
        r = session.post(LOGIN, data=formdata)
        r.raise_for_status()

        # 3] login with username and password
        formdata = get_formdata(r.text)
        formdata['u'] = username
        formdata['p'] = password
        r = session.post(LOGIN, data=formdata)
        r.raise_for_status()
    except:
        # TODO bad login does not raise exception
        raise
    else:
        return session


if __name__ == '__main__':
    main()
