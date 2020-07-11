# -*- coding: utf-8 -*-

import os

from portfolioapi import stockquotes

def test_aa_store_all_quotes(client):
    response = client.get('/update-quotes')
    assert response.data == b'ok\n'
