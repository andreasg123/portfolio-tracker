# -*- coding: utf-8 -*-

import json
import os


def test_get_report(client):
    response = client.get('/get-report?account=combined&year=2019')
    with open(os.path.join(os.path.dirname(__file__),
                           'get_report.json')) as f:
        expected = json.load(f)
    print(response.data)
    assert json.loads(response.data) == expected
