#!/usr/bin/python3

import datetime
import json
import os
import sys
import traceback

from portfolio import Portfolio, Transaction
from stockquotes import getQuotes


query_params = {x.split('=')[0]: x.split('=')[1]
                for x in os.environ['QUERY_STRING'].split('&') if x}
account = query_params.get('account', 'ag-broker')
year = query_params.get('year', str(datetime.date.today().year))

sys.stdout.write('Content-type: application/json\n')
sys.stdout.write('\n')
sys.stdout.flush()

try:
    # raise ValueError('abc')
    date = Transaction.parseDate(year + '-12-31')
    portfolio = Portfolio(date)
    files = []
    if account == 'combined':
        files = Transaction.getAccounts()
    else:
        files.append(account)
    all_buckets = []
    for f in files:
        portfolio.account = f
        t = Transaction.readTransactions(os.path.join('data', f), date)
        portfolio.fillBuckets(t)
        all_buckets.append(portfolio.buckets)
        portfolio.emptyBuckets()
    portfolio.combineBuckets(all_buckets)
    data = portfolio.toDict(year=year)
    data['year'] = year
    data['account'] = account
    data['quotes'] = getQuotes(datetime.date(int(year), 12, 31))
except:
    type, value, tb = sys.exc_info()
    data = {'error': traceback.format_exception(type, value, tb)}

json_data = json.dumps(data, separators=(',', ':'))
sys.stdout.write(json_data)
