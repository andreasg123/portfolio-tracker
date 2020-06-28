# -*- coding: utf-8 -*-

import json
import os


def test_get_accounts(client):
    response = client.get('/get-accounts')
    with open(os.path.join(os.path.dirname(__file__),
                           'get_accounts.json')) as f:
        expected = json.load(f)
    print(response.data)
    assert json.loads(response.data) == expected
