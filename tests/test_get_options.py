# -*- coding: utf-8 -*-

import json
import os


def test_get_options(client):
    response = client.get('/get-options?account=account2&date=2019-12-31')
    with open(os.path.join(os.path.dirname(__file__),
                           'get_options.json')) as f:
        expected = json.load(f)
    print(response.data)
    assert json.loads(response.data) == expected
