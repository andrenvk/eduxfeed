from .auth import session_api

import re

from bs4 import BeautifulSoup


API = 'https://kosapi.fit.cvut.cz'
UMAPI = API + '/usermap/v1'
KOSAPI = API + '/api/3'


def edux_author(username, session=None):
    """
    Retrieves real name from username using Usermap API

    Args:
        username (str): CTU username
        session (obj): authenticated API session (if available)

    Returns:
        name (dict): name and surname (dict keys 'first' and 'last'), None if not available
    """

    if not session:
        session = session_api()

    try:
        r = session.get(UMAPI + '/people/{username}'.format(username=username))
        r.raise_for_status()
        json = r.json()
        name = {
            'first': json['firstName'].split(' ')[0],
            'last': json['lastName'].split(' ')[-1],
        }
    except:
        # caller has to resolve if no response
        # do not pass -- name need not be empty
        return None

    return name


def user_enrolled(username, session=None):
    """
    Retrieves currently enrolled courses of a student using KOS API

    Args:
        username (str): CTU username
        session (obj): authenticated API session (if available)

    Returns:
        courses (list): list of course codes (e.g. MI-PYT), None if not available
    """

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
