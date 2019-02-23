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
date = query_params.get('date', datetime.date.today().isoformat())

sys.stdout.write('Content-type: application/json\n')
sys.stdout.write('\n')
sys.stdout.flush()

try:
    d = Transaction.parseDate(date)
    portfolio = Portfolio(d)
    files = []
    if account == 'combined':
        files = Transaction.getAccounts()
    else:
        files.append(account)
    all_buckets = []
    for f in files:
        portfolio.account = f
        t = Transaction.readTransactions(os.path.join('data', f), d)
        portfolio.fillBuckets(t)
        all_buckets.append(portfolio.buckets)
        portfolio.emptyBuckets()
    portfolio.combineBuckets(all_buckets)
    data = portfolio.toDict(all=True)
    data['account'] = account
    data['date'] = date
    historical = set(ab.end_date for ab in portfolio.assigned_buckets)
    data['quotes'] = getQuotes(Transaction.toDate(d))
    hq = {d.isoformat(): getQuotes(d)
          for d in (Transaction.toDate(h) for h in historical)}
    data['historical_quotes'] = hq
except:
    type, value, tb = sys.exc_info()
    data = {'error': traceback.format_exception(type, value, tb)}

json_data = json.dumps(data, separators=(',', ':'))
sys.stdout.write(json_data)
