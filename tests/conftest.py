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
