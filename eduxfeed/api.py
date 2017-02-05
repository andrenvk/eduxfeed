from .auth import session_api

import re

from bs4 import BeautifulSoup


API = 'https://kosapi.fit.cvut.cz'
UMAPI = API + '/usermap/v1'
KOSAPI = API + '/api/3'


def edux_author(username, session=None):
    if not session:
        session = session_api()

    try:
        r = session.get(UMAPI + '/people/{username}'.format(username=username))
        r.raise_for_status()
        json = r.json()
        name = {
            'first': json['firstName'],
            'last': json['lastName'],
        }
    except:
        # caller has to resolve if no response
        # do not pass -- name need not be empty
        return None

    return name


def user_enrolled(username, session=None):
    if not session:
        session = session_api()

    try:
        r = session.get(KOSAPI + '/students/{username}/enrolledCourses'.format(username=username))
        r.raise_for_status()
    except:
        # no known courses in case of error
        # otherwise user is not enrolled
        return None

    courses = []
    parser = BeautifulSoup(r.text, 'html.parser')
    for course in parser.find_all('course'):
        code = re.sub('^.+/', '', course['xlink:href'].rstrip('/'))
        courses.append(code)
    courses.sort()

    return courses
