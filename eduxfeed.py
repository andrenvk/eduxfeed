import re
import sys
import os.path
import datetime
import configparser

# import lxml
import requests
from bs4 import BeautifulSoup

KOSAPI = 'https://kosapi.fit.cvut.cz/api/3'


def main():
    username, password = auth(target='kosapi')
    sess, exp = session_kosapi(username, password)
    user_get_subjects(sess)

    # TODO update session
    # kosapi - expiration time
    # edux - check if still auth'd

    # TODO test edux
    # sess = session_kosapi(*auth())
    # print(sess.get('https://edux.fit.cvut.cz/courses/BI-ZUM/feed.php').text)

    # TODO test kosapi
    # sess, exp = session_kosapi(*auth(section='kosapi'))
    # r = sess.get("https://kosapi.fit.cvut.cz/api/3/courses/MI-MVI.16/parallels" +
    #              "?sem=B161&limit=25&access_token=52a6a7da-447b-477c-9298-48e81baacae0")
    # print(r.request.headers)


def auth(auth_file='./auth.cfg', target='edux', debug=True):
    config = configparser.ConfigParser()
    try:
        config.read(auth_file)
        username = config[target]['username']
        password = config[target]['password']
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


def session_edux(username, password):
    url = 'https://edux.fit.cvut.cz/start?do=login'
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
        'scope': 'cvut:kosapi:read',
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


def user_username():
    pass


def user_courses(sess):
    username = 'novako20' # user_username()
    r = sess.get(KOSAPI + '/students/{}/enrolledCourses'.format(username))
    # TODO tutorial error -- POST method error 405 Not Allowed
    # https://auth.fit.cvut.cz/manager/app-types.xhtml#service-account
    parser = BeautifulSoup(r.text, "lxml-xml")

    courses = {}
    for course in parser.find_all('course'):
        code = re.sub('^.+/', '', course.get('xlink:href').rstrip('/'))
        courses[code] = course.text

    return courses


if __name__ == '__main__':
    main()
