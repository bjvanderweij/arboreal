import bs4
import requests
import inspect
import hashlib
import getpass
import os
import keyring
import time
import arboral

from typing import Optional, Any, List, Iterator
from urllib.parse import urlparse

class LoginSession(arboral.Context, requests.Session):

    def __init__(self, login_url, username_field='username', password_field='password', username=None, other_fields={}):
        super().__init__()
        self.login_url = login_url
        self.username_field = username_field
        self.password_field = password_field
        self.username = username
        self.other_fields = other_fields

    def _get_login_details(self):
        if self.username is None:
            self.username = input(f'Enter username: ')
        password = keyring.get_password(self.login_url, self.username)
        if password is None:
            password = getpass.getpass()
            keyring.set_password(self.login_url, self.username, password)
        return self.username, password

    def _login(self, session):
        username, password = self._get_login_details()
        session.post(self.login_url, data={
                self.username_field:self.username,
                self.password_field:password,
                **self.other_fields
            })

    def _setup(self, session):
        pass

    def __enter__(self) -> requests.Session:
        session = super().__enter__()
        self._setup(session)
        self._login(session)
        return session

class GithubSession(LoginSession):

    def __init__(self, username=None):
        super().__init__(
                login_url="https://github.com/session",
                username_field="login"
            )

    def _setup(self, session):
        html = session.get(self.login_url).text
        soup = bs4.BeautifulSoup(html, features='html5lib')
        login_form = soup.select('form[action="/session"]')[0]
        self.other_fields = {
                'authenticity_token':login_form.select('input[name=authenticity_token]')[0]['value'],
                'timestamp':login_form.select('input[name=timestamp]')[0]['value'],
                'timestamp_secret':login_form.select('input[name=timestamp_secret]')[0]['value'],
            }


class Session(arboral.Context, requests.Session):

    def __init__(self, login_url, **params):
        super().__init__()
        self.login_url = login_url
        self.params = params

    def __enter__(self) -> requests.Session:
        session = super().__enter__()
        data = {}
        for k, v in self.params.items():
            if v == '{PROMPT}':
                v = input(f'Enter value for "{k}": ')
            elif v == '{PW_PROMPT}':
                v = getpass.getpass()
            data[k] = v
        print(self.login_url)
        r = session.post(self.login_url, data=data)
        print(session.cookies)
        return session

class ElementProperty(arboral.Singleton):

    def __init__(self, value):
        self.value = value

    def __call__(self, element: bs4.BeautifulSoup) -> bs4.BeautifulSoup:
        if self.value == 'text': # return the text
            return element.text
        elif self.value[0] == '.': # return an attribute
            return element[self.value[1:]]
        else:
            raise Exception()

TIMEOUT = 5
FETCH_MANAGER = {}

class Fetch(arboral.Singleton):

    def __init__(self, url: str, cache = False):
        self.url = url
        self.cache = cache

    @property
    def domain(self):
        return urlparse(self.url).hostname

    def sleep(self, amount):
        time.sleep(amount)

    def await_permission(self):
        t = time.time()
        if self.domain in FETCH_MANAGER:
            elapsed = t - FETCH_MANAGER[self.domain]
            if elapsed < TIMEOUT:
                self.sleep(TIMEOUT - elapsed)
        FETCH_MANAGER[self.domain] = t

    def __call__(self, session: Optional[requests.Session] = None) -> str:
        self.await_permission()
        #print(f'Fetching {self.url}')
        os.makedirs('cache', exist_ok=True)
        path = os.path.join('cache', hashlib.md5(self.url.encode()).hexdigest())
        if not os.path.exists(path) or not self.cache:
            if session is None:
                resp = requests.get(self.url)
            else:
                resp = session.get(self.url)
            with open(path, 'w') as f:
                f.write(resp.text)
        with open(path) as f:
            return f.read()

class Parse(arboral.Singleton):

    def __call__(self, html: str) -> bs4.BeautifulSoup:
        return bs4.BeautifulSoup(html, features='html5lib')

def resolve_value(value: str, element: bs4.BeautifulSoup) -> str:
    if value == 'text': # return the text
        return element.text
    if value == 'text_clean': # return the text with newlines and surrounding whitespace removed
        return " ".join(element.text.strip().split())
    if value[0] == '.': # return an attribute
        return element[value[1:]]

class Selector():

    def __init__(self, selector: str, value: Optional[str] = None):
        self.selector = selector
        self.value = value

    def select(self, element: bs4.BeautifulSoup) -> bs4.BeautifulSoup:
        selection = element.select(self.selector)
        if self.value is None:
            return iter(selection)
        return (resolve_value(self.value, e) for e in selection)


class SelectElement(Selector, arboral.Singleton):

    def __call__(self, element: bs4.BeautifulSoup) -> bs4.BeautifulSoup:
        return next(self.select(element))


class SelectElements(Selector, arboral.Iterator):

    def __call__(self, element: bs4.BeautifulSoup) -> Iterator[bs4.BeautifulSoup]:
        return self.select(element)


class Property(arboral.Singleton):

    def __init__(self, contents: str):
        self.contents = contents

    def __call__(self, element: bs4.BeautifulSoup) -> str:
        if self.contents == 'text':
            return parent_contents.text
        if self.contents[0] == '.':
            return parent_contents[self.contents[1:]]


class Scraper(arboral.DictParser):

    def __init__(self, scraper: dict, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.register(
                Session,
                LoginSession,
                GithubSession,
                Fetch,
                Parse,
                SelectElement,
                SelectElements,
                ElementProperty,
                Property,
            )
        self.ast = self.parse_dict(scraper)

    def evaluate(self):
        return arboral.evaluate(self.ast)
