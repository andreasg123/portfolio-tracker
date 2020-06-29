# -*- coding: utf-8 -*-

import json
import os


def test_get_history(client):
    response = client.get('/get-spy')
    with open(os.path.join(os.path.dirname(__file__),
                           'get_spy.json')) as f:
        expected = json.load(f)
    print(response.data)
    assert json.loads(response.data) == expected
