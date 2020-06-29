# -*- coding: utf-8 -*-

import pytest

# Without an empty "tests/__init__.py", this fails:
# ModuleNotFoundError: No module named 'portfolioapi'
from portfolioapi import create_app


@pytest.fixture
def app():
    app = create_app({
        'TESTING': True
    })
    return app


@pytest.fixture
def client(app):
    return app.test_client()


# https://www.mitchellcurrie.com/blog-post/python-mock-unittesting/

class MockHTTPResponse:
    # https://docs.python.org/3/library/urllib.request.html#urllib.request.urlopen

    def __init__(self, data=None, path=None):
        self.data = data
        self.path = path

    def info(self):
        headers = {}
        if self.path is not None and self.path.endswith('.gz'):
            headers['Content-Encoding'] = 'gzip'
        return headers

    def getcode(self):
        return 200 if data is not None or path is not None else 404

    def read(self):
        if self.path is not None:
            if self.path.endswith('.gz'):
                with open(self.path, 'rb') as f:
                    return f.read()
            else:
                with open(self.path, 'r') as f:
                    return f.read().encode()
        else:
            return self.data

    def close(self):
        pass
