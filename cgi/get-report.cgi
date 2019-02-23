#!/usr/bin/python3

from collections import defaultdict
import datetime
import json
import os
import sys
import traceback

from portfolio import Portfolio, Transaction
from stockquotes import getQuotes


query_params = {x.split('=')[0]: x.split('=')[1]
                for x in os.environ['QUERY_STRING'].split('&') if x}
account = query_params.get('account', 'all')
year = query_params.get('year', None)
date = query_params.get('date', None)

sys.stdout.write('Content-type: application/json\n')
sys.stdout.write('\n')
sys.stdout.flush()

try:
    # raise ValueError('abc')
    if year:
        date = year + '-12-31'
    elif not date:
        date = datetime.date.today().isoformat()
    files = []
    if account == 'all' or account == 'combined':
        files = Transaction.getAccounts()
    else:
        files.append(account)
    account_portfolios = {}
    all_buckets = []
    d = Transaction.parseDate(date)
    data = {}
    data['quotes'] = getQuotes(Transaction.toDate(d))
    data['oldquotes'] = getQuotes(Transaction.toDate(d - 1))
    quote_splits = set()
    if account == 'combined':
        portfolio = Portfolio(d)
        account_portfolios[account] = portfolio
    for f in files:
        portfolio.account = f
        trans = Transaction.readTransactions(os.path.join('data', f), d)
        if not trans:
            continue
        if account != 'combined':
            portfolio = Portfolio(d)
            account_portfolios[f] = portfolio
        portfolio.fillBuckets(trans)
        share_diff = defaultdict(float)
        for t in trans:
            if t.date != d:
                continue
            if t.type == 'b':
                share_diff[t.name] += t.count
            elif t.type == 's':
                share_diff[t.name] -= t.count
            elif (t.name not in quote_splits and t.type == 'x' and
                  (not t.name2 or t.name2 == t.name)):
                try:
                    quote_splits.add(t.name)
                    data['oldquotes'][t.name] /= (1 + t.amount1)
                except KeyError:
                    pass
        # print(share_diff)
        # print({k: data['oldquotes'].get(k) for k in share_diff})
        for k, v in share_diff.items():
            try:
                # equity_diff only represents sales.  Quote changes are
                # computed on the client.
                portfolio.equity_diff += v * data['oldquotes'][k]
            except KeyError:
                pass
        if account == 'combined':
            all_buckets.append(portfolio.buckets)
            portfolio.emptyBuckets()
    if account == 'combined':
        portfolio.combineBuckets(all_buckets)
    data['accounts'] = {k: v.toDict(year=year)
                        for k, v in account_portfolios.items()}
    if year:
        data['year'] = year
    else:
        data['date'] = date
    data['account'] = account
except:
    type, value, tb = sys.exc_info()
    data = {'error': traceback.format_exception(type, value, tb)}

json_data = json.dumps(data, separators=(',', ':'))
sys.stdout.write(json_data)
