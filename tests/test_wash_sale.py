# -*- coding: utf-8 -*-

import io

from portfolioapi.portfolio import Portfolio, Transaction

def test_wash_sale():
    year = 2012
    date = Transaction.parseDate('2012-12-31')
    data = '''12-02-29|b|AAPL120317C00540000|200|14.73|7.49
12-02-29|b|AAPL120317C00540000|100|14.71|3.73
12-03-05|s|AAPL120317C00540000|300|10|11.27
12-03-07|b|AAPL120317C00540000|300|9|11.22
12-03-08|s|AAPL120317C00540000|300|6.8|11.26
12-03-08|s|AAPL120317C00540000|200|8.08|1.55
12-03-08|b|AAPL120317C00540000|200|9.7|10.47
12-03-08|b|AAPL120317C00540000|300|9|11.22
12-03-14|s|AAPL120317C00540000|200|37.55|10.61
12-03-14|s|AAPL120317C00540000|100|38.14|0.82'''
    trans = Transaction.read(io.StringIO(data), date)
    portfolio = Portfolio(date)
    portfolio.fillLots(trans)
    yearend = portfolio.toDict(year=year)
    assert yearend['cash'] == 6143.36
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
    completed_lots = [
        {'symbol': 'AAPL120317C00540000', 'nshares': 200.0, 
         'start_share_price': 14.73, 'end_share_price': 10.0, 
         'start_share_expense': 0.03745, 'end_share_expense': 0.03756667, 
         'start_share_adj': 0, 'end_share_adj': -4.805, 'wash_sale': 4.805, 
         'wash_days': 0, 'start_date': '2012-02-29', 'end_date': '2012-03-05'},
        {'symbol': 'AAPL120317C00540000', 'nshares': 100.0, 
         'start_share_price': 14.71, 'end_share_price': 10.0, 
         'start_share_expense': 0.0373, 'end_share_expense': 0.03756667, 
         'start_share_adj': 0, 'end_share_adj': -4.7849, 'wash_sale': 4.7849, 
         'wash_days': 0, 'start_date': '2012-02-29', 'end_date': '2012-03-05'},
        {'symbol': 'AAPL120317C00540000', 'nshares': 200.0, 
         'start_share_price': 9.0, 'end_share_price': 6.8, 
         'start_share_expense': 0.0374, 'end_share_expense': 0.03753333, 
         'start_share_adj': 4.805, 'end_share_adj': -7.07995, 'wash_sale': 7.07995, 
         'wash_days': 5, 'start_date': '2012-03-07', 'end_date': '2012-03-08'},
        {'symbol': 'AAPL120317C00540000', 'nshares': 100.0, 
         'start_share_price': 9.0, 'end_share_price': 6.8, 
         'start_share_expense': 0.0374, 'end_share_expense': 0.03753333, 
         'start_share_adj': 4.7849, 'end_share_adj': -7.0598, 'wash_sale': 7.0598, 
         'wash_days': 5, 'start_date': '2012-03-07', 'end_date': '2012-03-08'},
        {'symbol': 'AAPL120317C00540000', 'nshares': -200.0, 
         'start_share_price': 8.08, 'end_share_price': 9.7, 
         'start_share_expense': 0.00775, 'end_share_expense': 0.05235, 
         'start_share_adj': 0, 'end_share_adj': 0, 'wash_sale': 0, 
         'wash_days': 0, 'start_date': '2012-03-08', 'end_date': '2012-03-08'},
        {'symbol': 'AAPL120317C00540000', 'nshares': 200.0, 
         'start_share_price': 9.0, 'end_share_price': 37.55, 
         'start_share_expense': 0.0374, 'end_share_expense': 0.05305, 
         'start_share_adj': 7.07995, 'end_share_adj': 0, 'wash_sale': 0, 
         'wash_days': 1, 'start_date': '2012-03-08', 'end_date': '2012-03-14'},
        {'symbol': 'AAPL120317C00540000', 'nshares': 100.0, 
         'start_share_price': 9.0, 'end_share_price': 38.14, 
         'start_share_expense': 0.0374, 'end_share_expense': 0.0082, 
         'start_share_adj': 7.0598, 'end_share_adj': 0, 'wash_sale': 0, 
         'wash_days': 1, 'start_date': '2012-03-08', 'end_date': '2012-03-14'}
    ]
    assert yearend['completed_lots'] == completed_lots
