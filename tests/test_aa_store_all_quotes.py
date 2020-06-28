# -*- coding: utf-8 -*-

import os

from portfolioapi import stockquotes

def test_aa_store_all_quotes(client):
    try:
        os.unlink(stockquotes.quote_db)
    except FileNotFoundError:
        pass
    stockquotes.storeAllQuotes()
