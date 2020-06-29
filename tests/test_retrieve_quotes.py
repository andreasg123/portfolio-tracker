# -*- coding: utf-8 -*-

from .conftest import MockHTTPResponse
import json
import mock
import os


def test_get_report(client):
    path = os.path.join(os.path.dirname(__file__), 'mock_quotes.json.gz')
    with mock.patch('urllib.request.urlopen',
                    return_value=MockHTTPResponse(path=path)) as mock_urlopen:
        response = client.get('/retrieve-quotes?force=true')
        assert mock_urlopen.call_count == 1
