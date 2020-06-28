# -*- coding: utf-8 -*-

import json
import os


def test_get_annual(client):
    response = client.get('/get-annual?account=account2&year=2019&skip=options')
    with open(os.path.join(os.path.dirname(__file__),
                           'get_annual.json')) as f:
        expected = json.load(f)
    print(response.data)
    assert json.loads(response.data) == expected
