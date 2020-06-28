# -*- coding: utf-8 -*-

import os

from portfolioapi import portfolio

def test_portfolio_utility(client):
    # Using the "client" fixture changes "portfolio.data_dir"
    cache_dir = os.path.join(portfolio.data_dir, 'cache')
    for a in ['account1', 'account2']:
        try:
            os.unlink(os.path.join(cache_dir, a + '.db'))
        except FileNotFoundError:
            pass
    portfolio.main(['', 'account2', '2012-01-01', '2019-12-31'])
    portfolio.main2(['', 'account2', '2019-12-31'])
    path = os.path.join(portfolio.data_dir, 'account2')
    portfolio.Transaction.checkTransactions(path)
    portfolio.Transaction.checkOptions(path)
    # These tests only provide coverage for utility functions.
