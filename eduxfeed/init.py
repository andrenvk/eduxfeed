from . import db
from .auth import EDUX
from .auth import session_edux
from .update import edux_check_pages, edux_check_media

import re

import requests
from bs4 import BeautifulSoup


def init():
    """
    Initializes database

    To be run only once at the very beginning.
    Gets a list of EDUX courses and for each course
    saves its current state (last page update and list of files).

    Args:
        None
    """
    db.init()
    courses = edux_courses()
    session = session_edux()
    edux_init_pages(courses, session)
    edux_init_media(courses, session)


def edux_courses():
    """
    Gets a list of EDUX courses

    Parses the courses from EDUX home webpage,
    the agent must not be authenticated.

    Args:
        None

    Returns:
        courses (list): list of course codes
    """
    r = requests.get(EDUX)
    parser = BeautifulSoup(r.text, 'html.parser')

    courses = []
    for div in parser.find_all('div', {'class': 'courselist_field'}):
        table = div.table
        if table:
            for course in table.find_all('a'):
                code = course.text.strip()
                # no BIK- subjects and alike / TV course / MI-SPI-1
                if re.match('[^-]+K-', code) or len(code.split('-')) != 2:
                    continue
                courses.append(code)

    return courses


def edux_init_pages(courses, session):
    """
    Initialize state of EDUX course pages

    Utilizes :func:`.update.edux_check_pages` to get the
    last timestamp from the course feed on EDUX.

    Args:
        courses (list): list of course codes
        session (obj): authenticated EDUX session
    """
    pages = db.edux_pages()
    pages['COURSES'] = {}
    for course in courses:
        print('PAGES', course)
        last = edux_check_pages(course, session, authors=None, timestamp=None)
        if last is None:
            last = 0
        pages['COURSES'][course] = str(last)
    db.edux_pages_set(pages)


def edux_init_media(courses, session):
    """
    Initialize state of EDUX course files

    Utilizes :func:`.update.edux_check_media` to get the
    list of files uploaded to the course on EDUX.

    Args:
        courses (list): list of course codes
        session (obj): authenticated EDUX session
    """
    for course in courses:
        print('MEDIA', course)
        media = db.edux_media(course)
        media[course] = {}
        db.edux_media_set(course, media)
        _ = edux_check_media(course, session)
