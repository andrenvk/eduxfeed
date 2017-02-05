from . import db
from .auth import EDUX
from .auth import session_edux
from .update import edux_check_pages, edux_check_media

import re

import requests
from bs4 import BeautifulSoup


def init():
    db.init()
    courses = edux_courses()
    session = session_edux()
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
                # no BIK- subjects and alike / TV course / MI-SPI-1
                if re.match('[^-]+K-', code) or len(code.split('-')) != 2:
                    continue
                courses.append(code)

    return courses


def edux_init_pages(courses, session):
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
    for course in courses:
        print('MEDIA', course)
        media = db.edux_media(course)
        media[course] = {}
        db.edux_media_set(course, media)
        _ = edux_check_media(course, session)
