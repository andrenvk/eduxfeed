from eduxfeed.auth import EDUX
from eduxfeed import auth

import re
import requests
from bs4 import BeautifulSoup

import pytest


@pytest.mark.parametrize(
    ['session_creator', 'should_fail'],
    [
        (auth.session_edux, False),
        (requests.Session, True),
    ],
)
def test_session_edux(session_creator, should_fail):
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
    username, password = auth.auth(target='api')
    session = auth.session_api(username, password)
    assert 'Authorization' in session.headers
