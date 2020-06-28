# -*- coding: utf-8 -*-

import json
import os


def test_get_taxes(client):
    response = client.get('/get-taxes?account=account2&year=2019')
    with open(os.path.join(os.path.dirname(__file__),
                           'get_taxes.json')) as f:
        expected = json.load(f)
    print(response.data)
    assert json.loads(response.data) == expected
