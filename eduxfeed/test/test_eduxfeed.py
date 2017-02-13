from eduxfeed.auth import AUTH_FILE, EDUX
from eduxfeed import auth
from eduxfeed import appweb
from eduxfeed import appcode
from eduxfeed.update import edux_page_prev, edux_feed_last

import os
import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup

import pytest
import flexmock


FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures')

AUTH_SAMPLE = os.path.join(FIXTURES, 'auth.cfg.sample')
AUTH = AUTH_FILE if auth.auth() else AUTH_SAMPLE

OPEN = {
    'mode': 'r',
    'encoding': 'utf-8',
}


# TEST AUTH


@pytest.mark.parametrize(
    ['target', 'file'],
    [(target, AUTH) for target in ('edux', 'api', 'oauth')],
)
def test_config(target, file):
    credentials = auth.auth(target, file)
    assert len(credentials) == 2 if target != 'oauth' else 3


def test_config_fail():
    with pytest.raises(KeyError):
        auth.auth('non-existent-section', AUTH)


def skip_auth(auth_file):
    if auth_file == AUTH_SAMPLE:
        pytest.skip('test only using real credentials')


@pytest.mark.parametrize(
    ['session_creator', 'should_fail'],
    [
        (requests.Session, True),
        (auth.session_edux, False),
    ],
)
def test_session_edux(session_creator, should_fail):
    skip_auth(AUTH)
    username, password = auth.auth(target='edux')
    session = session_creator()
    r = session.get(EDUX)
    r.raise_for_status()
    parser = BeautifulSoup(r.text, 'html.parser')
    div = parser.find('div', {'class': 'user'})
    text = div.text.strip()
    if should_fail:
        assert not len(text) > 0
        assert not re.search(username, text)
    else:
        assert len(text) > 0
        assert re.search(username, text)


def test_session_api():
    skip_auth(AUTH)
    username, password = auth.auth(target='api')
    session = auth.session_api(username, password)
    assert 'Authorization' in session.headers


# TEST APPCODE


@pytest.mark.parametrize(
    ['files', 'valid'],
    [
        (('.dotfile', '_file', 'also_file', 'file_'), 0),
        (('user0.txt', 'user1.txt', 'user2.txt'), 3),
        (('user0.txt', 'user1.txt', 'user2.py'), 2),
        (('dotfile.', 'normal.txt'), 1),
        ((), 0),
    ],
)
def test_user_list(files, valid):
    # update according to db.user_list
    users = [f.split('.txt')[0] for f in files if not (re.search('_', f) or re.match('\.', f))]
    users = [u for u in users if re.match('^[a-z0-9]+$', u)]
    assert len(users) == valid


@pytest.mark.parametrize(
    ['path', 'output'],
    [
        ('MI-PYT/x/y/z', 'x/y/z'),
        ('MI-PYT/x/y/z/', 'x/y/z'),
        ('MI-PYT/lectures/start', 'lectures'),
        ('MI-PYT/lectures', 'lectures'),
        ('MI-PYT/start', 'MI-PYT'),
        ('MI-PYT/', 'MI-PYT'),
        ('MI-PYT', 'MI-PYT'),
        ('MI-PYT/_media/en/file', 'en/file'),
        ('MI-PYT/_media/file.txt', 'file.txt'),
        # should not happen, should start w/ code
        ('/_media/file.txt', '/_media/file.txt'),
    ],
)
def test_filter_path(path, output):
    f = appweb.filter_path
    assert f(path) == output


@pytest.mark.parametrize(
    ['target', 'escape'],
    [(t, e) for t in ('TARGET', None) for e in (True, False)],
)
def test_filter_link(target, escape):
    ITEM = {
        'src': 'SRC',
        'code': 'CODE',
        'path': 'PATH',
        'item': {
            'from': 123,
            'to': 321,
            'hash': 'HASH',
        }
    }
    with appweb.app.test_request_context():
        link = str(appweb.filter_link(ITEM, 'USERNAME', target, escape))
        assert re.match('http', link)
        # assert len(link.split('?')) == 2
        path, query = link.split('?')
        # assertion based on current logic
        assert re.search('USERNAME', path)
        assert '&' in query
        if escape:
            assert re.search('&[a-z]+;', query)
        if target:
            assert re.search('target={}$'.format(target), query)
        for k, v in ITEM.items():
            if type(v) is not dict:
                assert '{}={}'.format(k, v) in query
            else:
                for kk, vv in v.items():
                    assert '{}={}'.format(kk, vv) in query


@pytest.mark.parametrize(
    ['update', 'current'],
    [(x, y) for x in ({}, {'key': True}, {'key': False}) for y in ({}, {'key': True}, {'key': False})],
)
def test_user_update_key(update, current):
    # update according to appcode.user_update
    key = 'key'
    if key in update:
        current[key] = True
    elif current.get(key, True):
        # key disabled
        assert key not in update and current.get(key, True)
        current[key] = False

    if key in update:
        assert current[key]
    else:
        assert not current[key]


@pytest.mark.parametrize(
    ['dict_in', 'dict_out'],
    [
        # 1
        ({
            'key': {
                'course': {
                    'NON-MATCH': [0, ()],
                    'MATCHthat': 'string',
                    'MATCHpath': {'int': 1, 'list': [], 'dict': {}},
                },
                'non': {'NON-MATCH': []},
                'yep': {'MATCH': 'M'},
                'nope': {},
            }
        }, {
            'key': {
                'course': {
                    'NON-MATCH': [0, ()],
                },
                'non': {'NON-MATCH': []},
            }
        }),

        # 2
        ({
            'key': {
                'course': {
                    'NON-MATCH': 0,
                },
                'non': {'NON-MATCH': []},
            }
        }, {
            'key': {
                'course': {
                    'NON-MATCH': 0,
                },
                'non': {'NON-MATCH': []},
            }
        }),

        # 3
        ({
            'key': {
                0: {'MATCH': 1},
                1: {'MATCHagain': ()},
            },
            'src': {
                2: {'MATCH': 'match'},
            }
        }, {
            'key': {},
            'src': {},
        }),

        # 4
        ({
            'non-key': {
                0: {'MATCH': 1},
            },
            'src': {},
        }, {
            'non-key': {
                0: {'MATCH': 1},
            },
            'src': {},
        }),
    ]
)
def test_user_update_dict(dict_in, dict_out):
    # update according to appcode.user_update
    feed = dict_in
    for src in ('src', 'key'):
        if src in feed:
            delete = {}
            for course in feed[src]:
                delete[course] = []
                for path in feed[src][course]:
                    if re.match('MATCH', path):
                        delete[course].append(path)
            for course in delete:
                for key in delete[course]:
                    del feed[src][course][key]
                if not feed[src][course]:
                    del feed[src][course]

    assert dict_in == dict_out


@pytest.mark.parametrize(
    ['dict_in', 'item', 'dict_out'],
    [
        # 1
        ({
            'from': 10,
            'to': 20,
            'updates': {
                15: 'whatever',
                20: 'current',
            }
        }, {'to': 15}, {
            'from': 15,
            'to': 20,
            'updates': {
                20: 'current',
            }
        }),

        # 2
        ({
            'from': 10,
            'to': 20,
            'updates': {
                15: 'whatever',
                20: 'current',
            }
        }, {'to': 14}, {
            'from': 14,
            'to': 20,
            'updates': {
                15: 'whatever',
                20: 'current',
            }
        }),

        # 3
        ({
            'from': 10,
            'to': 20,
            'updates': {
                15: 'whatever',
                20: 'current',
            }
        }, {'to': 1}, {
            'from': 10,
            'to': 20,
            'updates': {
                15: 'whatever',
                20: 'current',
            }
        }),

        # 4
        ({
            'from': 10,
            'to': 20,
            'updates': {
                15: 'whatever',
                20: 'current',
            }
        }, {'to': 20}, {
            # remove
        }),
    ]
)
def test_item_markread(dict_in, item, dict_out):
    # update according to appcode.item_markread
    item.update({'src': 0, 'code': 1, 'path': 2})
    if dict_out:
        dict_out = {0: {1: {2: dict_out}}}
    dict_in = {0: {1: {2: dict_in}}}
    feed = dict_in

    skip = False
    try:
        src = feed[item['src']]
        code = src[item['code']]
        path = code[item['path']]
    except:
        # already deleted from feed
        skip = True

    if not skip:
        to = int(item['to'])
        if to == path['to']:
            # remove item completely
            # possible cascade delete
            del code[item['path']]
            if not code:
                del src[item['code']]
            if not src:
                del feed[item['src']]
        else:
            # feed has new updates
            delete = []
            for timestamp in path['updates']:
                if not timestamp > to:
                    delete.append(timestamp)
            for key in delete:
                del path['updates'][key]
            if path['from'] < to:
                path['from'] = to

    assert dict_in == dict_out


@pytest.mark.parametrize(
    ['path', 'should_match'],
    [
        ('MI-PYT/classification', False),
        ('MI-PYT/classification/', False),
        ('MI-PYT/en/classification', False),
        ('MI-PYT/en/classification/', False),
        ('MI-PYT/classification/student', False),
        ('MI-PYT/classification/student/', True),
        ('MI-PYT/en/classification/student', False),
        ('MI-PYT/en/classification/student/', True),
        ('MI-PYT/classification/student/username', True),
        ('MI-PYT/en/classification/student/username/', True),
        ('MI-PYT/classification/view/fulltime', True),
        ('MI-PYT/classification/view/', True),
        ('MI-PYT/classification/view', False),
        ('/classification/student/', False),
        # beware, should not happen, however
        ('classification/student/', True),
        ('/classification/view/', False),
        ('classification/view/', False),
        ('/en/classification/', False),
        ('en/classification/', False),
        ('MI-PYT/en', False),
        ('MI-PYT/en/', False),
        ('MI-PYT/student', False),
        ('MI-PYT/student/', True),
        ('MI-PYT/en/student', False),
        ('MI-PYT/en/student/', True),
        ('MI-PYT/student/username', True),
        ('MI-PYT/student/username/', True),
        ('MI-PYT/en/student/username', True),
        ('MI-PYT/en/student/username/', True),
        ('MI-PYT/cs/student/username/', False),
        ('MI-PYT/student/username/namespace', True),
        ('MI-PYT/en/student/username/namespace', True),
    ],
)
def test_regex_ignored(path, should_match):
    # update according to update.edux_check_pages
    # and possibly update.edux_check_media if different pattern
    if (re.match('[^/]+/(en/)?classification/student/', path) or
        re.match('[^/]+/(en/)?classification/view/', path) or
        re.match('[^/]+/(en/)?student/', path)):
        # PEP 8 inconclusive about this indent
        assert should_match
    else:
        assert not should_match


@pytest.mark.parametrize(
    ['link', 'expected_link', 'expected_path', 'expected_rev'],
    [
        (
            'https://edux.fit.cvut.cz/courses/MI-PYT/tutorials/01_requests_click?rev=1485603601',
            EDUX + '/courses/MI-PYT/tutorials/01_requests_click?rev=1485603601',
            'MI-PYT/tutorials/01_requests_click',
            1485603601,

        ),
        (
            '/courses/MI-PYT/tutorials/01_requests_click?rev=1485603601',
            EDUX + '/courses/MI-PYT/tutorials/01_requests_click?rev=1485603601',
            'MI-PYT/tutorials/01_requests_click',
            1485603601,
        ),
        (
            '/courses/MI-PYT?rev=1485603601',
            EDUX + '/courses/MI-PYT?rev=1485603601',
            'MI-PYT',
            1485603601,
        ),
        (
            '/courses/MI-PYT/whatever?nonrev=123',
            EDUX + '/courses/MI-PYT/whatever?nonrev=123',
            'MI-PYT/whatever',
            None,
        ),
        (
            '/courses/MI-PYT/whatever?rev=abc',
            EDUX + '/courses/MI-PYT/whatever?rev=abc',
            'MI-PYT/whatever',
            None,
        ),
    ],
)
def test_regex_links(link, expected_link, expected_path, expected_rev):
    # update according to update.edux_check_pages
    # and possibly update.edux_check_media if different pattern
    link = re.sub('^.*?/courses/', EDUX + '/courses/', link)
    path = re.sub('^.*?/courses/', '', link)
    path = re.sub('\?.*$', '', path)
    assert link == expected_link
    assert path == expected_path
    if expected_rev is None:
        with pytest.raises(AttributeError):
            rev = int(re.search('\?(.+&)?rev=(\d+)', link).group(2))
    else:
        rev = int(re.search('\?(.+&)?rev=(\d+)', link).group(2))
        assert rev == expected_rev


# TEST PARSING


def fixture_files(target):
    targets = {
        'edux': 'edux[^_]',
        'feeds': 'edux_feed',
        'revisions': 'edux_rev',
        'courses': 'edux_courses',
        'ajax_req': 'edux_ajax_req',
        'ajax_res': 'edux_ajax_res',
    }
    pattern = targets[target]
    files = [f for f in os.listdir(FIXTURES) if os.path.isfile(os.path.join(FIXTURES, f))]
    files = [os.path.join(FIXTURES, f) for f in files if re.match(pattern, f)]
    return files


@pytest.fixture(params=fixture_files('ajax_req'))
def ajax_fixture_req(request):
    file = request.param
    with open(file, **OPEN) as f:
        markup = f.read()
        yield markup


def test_ajax_req(ajax_fixture_req):
    # update according to update.edux_check_media
    namespaces = []
    markup = ajax_fixture_req
    parser = BeautifulSoup(markup, 'html.parser')
    for a in parser.find_all('a'):
        ns = a['href'].split('=')[-1]
        namespaces.append(ns)

    assert len(namespaces) == len(parser.find_all('a'))
    for namespace in namespaces:
        assert re.match('^[\w\d/]+$', namespace)


@pytest.fixture(params=fixture_files('ajax_res'))
def ajax_fixture_res(request):
    file = request.param
    with open(file, **OPEN) as f:
        markup = f.read()
        yield markup


def test_ajax_res(ajax_fixture_res):
    # update according to update.edux_check_media
    markup = ajax_fixture_res
    parser = BeautifulSoup(markup, 'html.parser')
    for div in parser.find_all('div', {'class': ['even', 'odd']}):
        info = div.span.i
        # implicit assertion about proper expansion
        date, time = info.text.replace('/', '-').split(' ')
        size, unit = info.next_sibling.string.strip('( )').split(' ')
        timestamp = int(datetime.strptime('{} {}'.format(date, time), '%Y-%m-%d %H:%M').timestamp())
        for item in (date, time, size, unit):
            assert item and item == item.strip()
        assert re.match('^\w+$', unit)
        assert re.match('^\d+([.,]\d+)?$', size)
        assert re.match('^\d+$', str(timestamp))


@pytest.fixture(params=fixture_files('edux'))
def edux_fixture(request):
    file = request.param
    with open(file, **OPEN) as f:
        markup = f.read()
        yield markup


@pytest.fixture(params=fixture_files('courses'))
def edux_courses(request):
    file = request.param
    with open(file, **OPEN) as f:
        courses = [c.strip() for c in f.readlines()]
        courses = [c for c in courses if c and c[0] != '#']
        yield courses


def test_edux_courses(edux_fixture, edux_courses):
    # update according to init.edux_courses
    parser = BeautifulSoup(edux_fixture, 'html.parser')
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

    assert sorted(courses) == sorted(edux_courses)


@pytest.fixture(params=fixture_files('feeds'))
def feed_fixture(request):
    file = request.param
    with open(file, **OPEN) as f:
        markup = f.read()
        result = int(file.split('_')[-1].split('.')[0])
        yield markup, result


def test_edux_feed_last(feed_fixture):
    feed, timestamp = feed_fixture
    last = edux_feed_last(feed)
    assert type(last) is int
    assert last == timestamp


@pytest.fixture(params=fixture_files('revisions'))
def rev_fixture(request):
    file = request.param
    with open(file, **OPEN) as f:
        markup = f.read()
        yield markup


@pytest.mark.parametrize(
    ['challenge', 'expected'],
    [
        # fixtures/edux_timestamps.txt
        # 1485882442 > 1485861739 > 1456087220 > ... > 1266103802
        (1485882442 + 1, 1485882442),
        (1485882442 + 0, 1485882442),
        (1485882442 - 1, 1485861739),
        (1485861739 + 1, 1485861739),
        (1485861739 + 0, 1485861739),
        (1485861739 - 1, 1456087220),
        (1266103802 + 1, 1266103802),
        (1266103802 + 0, 1266103802),
        (1266103802 - 1, 1266103802 - 1),
    ]
)
def test_edux_page_prev(rev_fixture, challenge, expected):
    session = flexmock(get=flexmock(raise_for_status=lambda: None, text=rev_fixture))
    result = edux_page_prev('whatever', session, challenge)
    assert result == expected
