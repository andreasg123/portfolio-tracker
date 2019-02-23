from collections import defaultdict
import datetime
from flask import Flask, jsonify, request, Response
from itertools import groupby
import json
import os
import sys
import traceback

from portfolio import Portfolio, Transaction, getOptionParameters
from stockquotes import getQuotes, retrieveQuotes

app = Flask(__name__.split('.')[0])

data_dir = '/var/www/html/portfolio/data'

@app.route('/get-accounts')
def get_accounts():
    try:
        files = get_files('all')
        data = {'accounts': files}
    except:
        type, value, tb = sys.exc_info()
        data = {'error': traceback.format_exception(type, value, tb)}
    return jsonify(data)


@app.route('/get-report')
def get_report():
    account = request.args.get('account', 'all')
    date = request.args.get('date')
    year = request.args.get('year')
    try:
        # raise ValueError('abc')
        if year:
            date = year + '-12-31'
        elif not date:
            date = datetime.date.today().isoformat()        
        files = get_files(account)
        if not account:
            account = files[0]
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
            trans = Transaction.readTransactions(os.path.join(data_dir, f), d)
            if not trans:
                continue
            if account != 'combined':
                portfolio = Portfolio(d)
                account_portfolios[f] = portfolio
            portfolio.account = f
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
    return jsonify(data)


@app.route('/get-taxes')
def get_taxes():
    account = request.args.get('account')
    year = request.args.get('year', str(datetime.date.today().year))
    try:
        # raise ValueError('abc')
        date = Transaction.parseDate(year + '-12-31')
        files = get_files(account)
        if not account:
            account = files[0]
        portfolio = init_portfolio(date, files)
        data = portfolio.toDict(year=year)
        data['year'] = year
        data['account'] = account
        data['quotes'] = getQuotes(datetime.date(int(year), 12, 31))
    except:
        type, value, tb = sys.exc_info()
        data = {'error': traceback.format_exception(type, value, tb)}
    return jsonify(data)


@app.route('/get-options')
def get_options():
    account = request.args.get('account')
    date = request.args.get('date', datetime.date.today().isoformat())
    try:
        d = Transaction.parseDate(date)
        files = get_files(account)
        if not account:
            account = files[0]
        portfolio = init_portfolio(d, files)
        data = portfolio.toDict(all=True)
        data['account'] = account
        data['date'] = date
        pairs = sorted((ab.end_date, getOptionParameters(ab.symbol)[0])
                       for ab in portfolio.assigned_buckets)
        historical = {k: set(x[1] for x in g)
                      for k, g in groupby(pairs, key=lambda x: x[0])}
        data['quotes'] = getQuotes(Transaction.toDate(d))
        hq = {Transaction.toDate(k).isoformat():
              getQuotes(Transaction.toDate(k), g)
              for k, g in historical.items()}
        data['historical_quotes'] = hq
    except:
        type, value, tb = sys.exc_info()
        data = {'error': traceback.format_exception(type, value, tb)}
    return jsonify(data)


@app.route('/retrieve-quotes')
def retrieve_quotes():
    date = Transaction.parseDate(datetime.date.today().isoformat())
    files = get_files('combined')
    portfolio = init_portfolio(date, files)
    force = request.args.get('force') == 'true'
    retrieveQuotes(portfolio.getCurrentSymbols(), force=force)
    return Response('ok\n', mimetype='text/plain')

    
def init_portfolio(date, files):
    portfolio = Portfolio(date)
    all_buckets = []
    for f in files:
        t = Transaction.readTransactions(os.path.join(data_dir, f), date)
        portfolio.account = f
        portfolio.fillBuckets(t)
        all_buckets.append(portfolio.buckets)
        portfolio.emptyBuckets()
    portfolio.combineBuckets(all_buckets)
    return portfolio


def get_files(account):
    if not account:
        return Transaction.getAccounts(data_dir)[:1]
    elif account == 'combined' or account == 'all':
        return Transaction.getAccounts(data_dir)
    else:
        return [account]
