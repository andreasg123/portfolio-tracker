from collections import defaultdict
import copy
import datetime
from flask import jsonify, request, Response
from itertools import groupby
import json
import os
import sys
import traceback

from . import app
from .portfolio import Portfolio, Transaction, getOptionParameters
from .stockquotes import getQuotes, retrieveQuotes

data_dir = '/var/www/html/portfolio/data'
api_dir = '/var/www/portfolioapi'

@app.route('/get-accounts')
def get_accounts():
    date = request.args.get('date')
    year = request.args.get('year')
    try:
        if year:
            date = year + '-12-31'
        elif not date:
            date = datetime.date.today().isoformat()
        d = Transaction.parseDate(date)
        files = Portfolio.get_files(data_dir, 'all', d)
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
    skip = request.args.get('skip')
    try:
        # raise ValueError('abc')
        if year:
            date = year + '-12-31'
        elif not date:
            date = datetime.date.today().isoformat()
        d = Transaction.parseDate(date)
        files = Portfolio.get_files(data_dir, account, d)
        if not account:
            account = files[0]
        account_portfolios = {}
        all_lots = []
        all_deposits = []
        data = {}
        data['quotes'] = getQuotes(Transaction.toDate(d))
        data['oldquotes'] = getQuotes(Transaction.toDate(d - 1))
        data['yearquotes'] = getQuotes(datetime.date(Transaction.toYear(d) - 1,
                                                     12, 31))
        quote_splits = set()
        portfolios = init_portfolios(d, files, skip=skip)
        for p in portfolios:
            share_diff = defaultdict(float)
            for t in p.transactions:
                if t.date != d or t.is_cash_like():
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
                    p.equity_diff += v * data['oldquotes'][k]
                except KeyError:
                    pass
        if account == 'combined':
            account_portfolios = {account: Portfolio.combine(portfolios)}
        else:
            account_portfolios = {p.account: p for p in portfolios}
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
    skip = request.args.get('skip')
    try:
        # raise ValueError('abc')
        date = Transaction.parseDate(year + '-12-31')
        files = Portfolio.get_files(data_dir, account, date)
        if not account:
            account = files[0]
        portfolio = Portfolio.combine(init_portfolios(date, files, skip=skip))
        data = portfolio.toDict(year=year)
        data['year'] = year
        data['account'] = account
        data['quotes'] = getQuotes(datetime.date(int(year), 12, 31))
    except:
        type, value, tb = sys.exc_info()
        data = {'error': traceback.format_exception(type, value, tb)}
    return jsonify(data)


@app.route('/get-annual')
def get_annual():
    try:
        data = get_annual2(request.args.get('account', 'all'),
                           request.args.get('year'),
                           request.args.get('skip'))
    except:
        type, value, tb = sys.exc_info()
        data = {'error': traceback.format_exception(type, value, tb)}
    return jsonify(data)


def get_annual2(account, year=None, skip=None):
    data = {'accounts': {}, 'account': account}
    symbols = defaultdict(lambda: set(['SPY', 'QQQ', 'QQQQ']))
    today = datetime.date.today()
    if year and int(year) < today.year:
        date = year + '-12-31'
    else:
        date = today.isoformat()
    d = Transaction.parseDate(date)
    files = Portfolio.get_files(data_dir, account, d)
    # Still need to implement "combined" (year loop outside file loop?)
    for f in files:
        trans = Transaction.readTransactions(os.path.join(data_dir, f), d, skip=skip)
        accounts = Portfolio.readTransfers(d, f, skip=skip)
        if not trans and not accounts:
            continue
        years = []
        for k, g in groupby(trans, key=lambda x: Transaction.toYear(x.date)):
            start = Transaction.fromYear(k)
            end = min(d, Transaction.fromYearEnd(k))
            p = Portfolio(end)
            start2 = 0
            for (d2, _, trans2) in accounts:
                end2 = min(end, d2)
                # print()
                # print(f, k, start, end, start2, end2)
                # print(p.toDict())
                p.fillLots([t for t in trans
                            if t.date > start2 and t.date <= end2])
                start2 = end2
                p2 = Portfolio(end2)
                p2.fillLots([t for t in trans2 if t.date <= end2])
                p = Portfolio.combine([p, p2])
            # print()
            # print(f, k, start, end, start2)
            # print(p.toDict())
            # print([t for t in trans if t.date > start2])
            p.fillLots([t for t in trans
                        if t.date > start2 and t.date <= end])
            year = p.toDict()
            year['start'] = start
            year['end'] = end
            year['year'] = k
            symbols[k].update(p.lots.keys())
            years.append(year)
        data['accounts'][f] = {'years': years, 'deposits': p.deposits}
    quotes = {}
    for k, v in symbols.items():
        quotes[k] = getQuotes(Transaction.toDate(min(d, Transaction.fromYearEnd(k))), v)
    data['quotes'] = quotes
    min_quote = min(quotes.keys())
    for k, v in data['accounts'].items():
        v['years'] = [x for x in v['years'] if x['year'] >= min_quote]
    dividends = {}
    for s in ['SPY', 'QQQ']:
        dividends[s] = [(t.date, t.amount1)
                        for t in Transaction.readTransactions(
                                os.path.join(api_dir,
                                             s.lower() + '-dividend'),
                                skip=skip)]
    data['index_dividends'] = dividends
    return data


@app.route('/get-spy')
def get_spy():
    spy = set(['SPY'])
    dividends = Transaction.readTransactions(os.path.join(api_dir, 'spy-dividend'))
    start_year = 1997
    today = datetime.date.today()
    d = Transaction.parseDate(today.isoformat())
    years = []
    for y in range(start_year, today.year + 1):
        end = min(d, Transaction.fromYearEnd(y))
        year = {}
        year['end'] = end
        year['year'] = y
        year['quotes'] = getQuotes(Transaction.toDate(end), spy)
        years.append(year)
    data = {'years': years,
            'dividends': [(t.date, t.amount1) for t in dividends]}
    return jsonify(data)


@app.route('/get-options')
def get_options():
    account = request.args.get('account')
    date = request.args.get('date', datetime.date.today().isoformat())
    try:
        d = Transaction.parseDate(date)
        files = Portfolio.get_files(data_dir, account, d)
        if not account:
            account = files[0]
        # No need to skip options because this is only useful for options
        portfolio = Portfolio.combine(init_portfolios(d, files))
        data = portfolio.toDict(all=True)
        data['account'] = account
        data['date'] = date
        pairs = sorted((lt.end_date, getOptionParameters(lt.symbol)[0])
                       for lt in portfolio.assigned_lots)
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


@app.route('/get-history')
def get_history():
    account = request.args.get('account')
    start = request.args.get('start', '1970-01-01')
    end = request.args.get('end', datetime.date.today().isoformat())
    include_positions = request.args.get('positions', '') == 'true'
    try:
        start = Transaction.parseDate(start)
        end = Transaction.parseDate(end)
        data = Portfolio.getHistory(account, start, end,
                                    include_positions=include_positions)
    except:
        type, value, tb = sys.exc_info()
        data = {'error': traceback.format_exception(type, value, tb)}
    return jsonify(data)


@app.route('/retrieve-quotes')
def retrieve_quotes():
    date = Transaction.parseDate(datetime.date.today().isoformat())
    files = Portfolio.get_files(data_dir, 'combined')
    portfolio = Portfolio.combine(init_portfolios(date, files))
    force = request.args.get('force') == 'true'
    retrieveQuotes(portfolio.getCurrentSymbols(), force=force)
    return Response('ok\n', mimetype='text/plain')


def init_portfolios(date, files, skip=None):
    # This approach prevents the detection of wash sales across
    # accounts. While those are wash sales, they are confusing and should
    # be avoided.
    portfolios = []
    for f in files:
        trans = Transaction.readTransactions(os.path.join(data_dir, f), date, skip=skip)
        accounts = Portfolio.readTransfers(date, f, skip=skip)
        if not trans and not accounts:
            continue
        portfolio = Portfolio(date)
        start = 0
        for end, _, trans2 in accounts:
            portfolio.fillLots([t for t in trans
                                if t.date > start and t.date <= end])
            start = end
            p = Portfolio(end)
            p.fillLots(trans2)
            portfolio = Portfolio.combine([portfolio, p])
        portfolio.fillLots([t for t in trans if t.date > start])
        portfolio.account = f
        portfolios.append(portfolio)
    return portfolios


if __name__ == '__main__':
    # retrieve_quotes()
    skip = None
    # skip = 'options'
    print(get_annual2('ag-broker', skip=skip))
