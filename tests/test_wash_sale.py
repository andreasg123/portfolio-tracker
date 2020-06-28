# -*- coding: utf-8 -*-

import io
import json
import os

from portfolioapi import portfolio


def test_wash_sale(client):
    # Using the "client" fixture changes "data_dir"
    year = 2012
    date = portfolio.Transaction.parseDate('2012-12-31')
    path = os.path.join(portfolio.data_dir, 'account1')
    trans = portfolio.Transaction.readTransactions(path, date)
    p = portfolio.Portfolio(date)
    p.fillLots(trans)
    yearend = p.toDict(year=year)
    # (200 * 10 - 7.5133) - (200 * 14.73 + 7.49) = -961.0033 (-4.805/share)
    # (100 * 10 - 3.7567) - (100 * 14.71 + 3.73) = -478.4867 (-4.7849/share)
    # Those adjustments are added to the cost basis of the next purchase.
    # 200 * 9 + 0.667 * 11.22 + 961.0033 = 2768.48
    # 100 * 9 + 0.333 * 11.22 + 478.4867 = 1382.23
    # 200 * 6.8 - 0.667 * 11.26 - 2768.48 = -1415.99 (-7.07995/share)
    # 100 * 6.8 - 0.333 * 11.26 - 1382.23 = -705.98 (-7.0598/share)
    # Accidental short sale and buyback not part of wash sales.
    # (200 * 8.08 - 1.55) - (200 * 9.7 + 10.47) = -336.02
    # Add wash sale loss to cost basis of next purchase.
    # 200 * 9 + 0.667 * 11.22 + 1415.99 = 3223.47
    # 100 * 9 + 0.333 * 11.22 + 705.98 = 1609.72
    # 200 * 37.55 - 10.61 - 3223.47 = 4275.92
    # 100 * 38.14 - 0.82 - 1609.72 = 2203.46
    # 2203.46 + 4275.92 - 336.02 = 6143.36
    #
    # Buy 100 OTEX @ 60.00 + 8.95 = 6008.95 (6143.36 - 6008.95 = 134.41)
    assert yearend['cash'] == 134.41
    print(json.dumps(yearend['completed_lots']))
    with open(os.path.join(os.path.dirname(__file__),
                           'wash_sale.json')) as f:
        expected = json.load(f)
    assert yearend['completed_lots'] == expected
