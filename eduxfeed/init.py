from . import db
from .auth import EDUX
from .auth import auth, session_edux
from .update import edux_check_media, edux_check_pages

import re

import requests
from bs4 import BeautifulSoup


def edux_init():
    courses = edux_courses()
    session = session_edux(*auth(target='edux'))
    edux_init_pages(courses, session)
    edux_init_media(courses, session)


def edux_courses():
    # must not be authenticated
    r = requests.get(EDUX)
    parser = BeautifulSoup(r.text, 'html.parser')

    courses = []
    for div in parser.find_all('div', {'class': 'courselist_field'}):
        table = div.table
        if table:
            for course in table.find_all('a'):
                code = course.text.strip()
                # no BIK- subjects and alike / TV course (if applicable)
                if re.match('[^-]+K-', code) or not re.search('-', code):
                    continue
                courses.append(code)

    return courses


def edux_init_pages(courses, session):
    pages = db.edux_pages()
    pages['COURSES'] = {}
    for course in courses:
        last = edux_check_pages(course, session, authors=None, timestamp=None)
        if last is None:
            last = 0
        pages['COURSES'][course] = str(last)
    db.edux_pages_set(pages)


def edux_init_media(courses, session):
    for course in courses:
        media = db.edux_media(course)
        media[course] = {}
        db.edux_media_set(media)
        _ = edux_media_check(course, session)
