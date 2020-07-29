# -*- coding: utf-8 -*-

from collections import defaultdict
import copy
import datetime
from flask import Blueprint, jsonify, request, Response
from itertools import groupby
import json
import os
import re
import sys
import traceback

from .portfolio import Portfolio, Transaction, getOptionParameters, data_dir, cache_dir
from .stockquotes import getQuotes, retrieveQuotes, storeAllQuotes, getDateQuotes

bp = Blueprint('views', __name__)


@bp.route('/get-accounts')
def get_accounts():
    date = request.args.get('date')
    year = request.args.get('year')
    try:
        date = get_date(date, year)
        d = Transaction.parseDate(date)
        files = Portfolio.get_files(data_dir, 'all', d)
        data = {'accounts': files}
    except:
        data = format_exception()
    return jsonify(data)


@bp.route('/get-report')
def get_report():
    account = request.args.get('account', 'all')
    date = request.args.get('date')
    year = request.args.get('year')
    skip = request.args.get('skip')
    try:
        date = get_date(date, year)
        d = Transaction.parseDate(date)
        y = Transaction.toYear(d)
        prev_year_end = Transaction.fromYearEnd(y - 1)
        files = Portfolio.get_files(data_dir, account, d)
        if not account:
            account = files[0]
        account_portfolios = {}
        all_lots = []
        all_deposits = []
        data = {}
        quote_splits = {}
        year_quote_splits = {}
        portfolios = init_portfolios(d, files, skip=skip)
        share_diffs = []
        # TODO: if a stock changes its symbol during the year, the year-end
        # quote for the old symbol has to be included.
        for p in portfolios:
            share_diff = defaultdict(float)
            share_diffs.append(share_diff)
            for t in p.transactions:
                if t.date <= prev_year_end or t.is_cash_like():
                    continue
                if t.type == 'x' and (not t.name2 or t.name2 == t.name):
                    year_quote_splits[t.name] = 1 / (1 + t.amount1)
                    if t.date == d:
                        quote_splits[t.name] = 1 / (1 + t.amount1)
                elif t.date != d:
                    continue
                if t.type == 'b':
                    share_diff[t.name] += t.count
                elif t.type == 's':
                    share_diff[t.name] -= t.count
        if account == 'combined':
            share_diff = defaultdict(float)
            for sd in share_diffs:
                for k, v in sd.items():
                    share_diff[k] += v
            share_diffs = [share_diff]
            portfolios = [Portfolio.combine(portfolios)]
            account_portfolios = {account: portfolios[0]}
        else:
            account_portfolios = {p.account: p for p in portfolios}
        symbols = set([s for p in portfolios for s in p.getCurrentSymbols()])
        data['quotes'] = getQuotes(Transaction.toDate(d), symbols)
        old_quotes = getQuotes(Transaction.toDate(d - 1), symbols)
        year_quotes = getQuotes(Transaction.toDate(prev_year_end), symbols)
        for k, v in quote_splits.items():
            try:
                old_quotes[k] *= v
            except KeyError:
                pass
        for k, v in year_quote_splits.items():
            try:
                year_quotes[k] *= v
            except KeyError:
                pass
        data['oldquotes'] = old_quotes
        data['yearquotes'] = year_quotes
        for i, p in enumerate(portfolios):
            share_diff = share_diffs[i]
            for k, v in share_diff.items():
                try:
                    # equity_diff only represents sales.  Quote changes are
                    # computed on the client.
                    p.equity_diff += v * data['oldquotes'][k]
                except KeyError:
                    pass
        data['accounts'] = {k: v.toDict(year=year)
                            for k, v in account_portfolios.items()}
        if year:
            data['year'] = year
        else:
            data['date'] = date
        data['account'] = account
    except:
        data = format_exception()
    return jsonify(data)


@bp.route('/get-taxes')
def get_taxes():
    account = request.args.get('account')
    year = request.args.get('year', str(datetime.date.today().year))
    skip = request.args.get('skip')
    try:
        date = Transaction.parseDate(get_date(None, year))
        files = Portfolio.get_files(data_dir, account, date)
        if not account:
            account = files[0]
        portfolio = Portfolio.combine(init_portfolios(date, files, skip=skip))
        data = portfolio.toDict(year=year)
        data['year'] = year
        data['account'] = account
        data['quotes'] = getQuotes(datetime.date(int(year), 12, 31))
    except:
        data = format_exception()
    return jsonify(data)


@bp.route('/get-annual')
def get_annual():
    try:
        data = get_annual2(request.args.get('account', 'all'),
                           request.args.get('year'),
                           request.args.get('skip'))
    except:
        data = format_exception()
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
                                os.path.join(cache_dir,
                                             s.lower() + '-dividend'),
                                skip=skip)]
    data['index_dividends'] = dividends
    return data


@bp.route('/get-spy')
def get_spy():
    end = request.args.get('end', datetime.date.today().isoformat())
    spy = set(['SPY'])
    dividends = Transaction.readTransactions(os.path.join(cache_dir, 'spy-dividend'))
    start_year = 1997
    today = datetime.date.today()
    d = Transaction.parseDate(end)
    next_year = Transaction.toYear(d) + 1
    years = []
    for y in range(start_year, next_year):
        end = min(d, Transaction.fromYearEnd(y))
        year = {}
        year['end'] = end
        year['year'] = y
        year['quotes'] = getQuotes(Transaction.toDate(end), spy)
        years.append(year)
    data = {'years': years,
            'dividends': [(t.date, t.amount1) for t in dividends]}
    return jsonify(data)


@bp.route('/get-options')
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
        data = format_exception()
    return jsonify(data)


@bp.route('/get-history')
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
        data = format_exception()
    return jsonify(data)


@bp.route('/clear-history')
def clear_history():
    account = request.args.get('account')
    Portfolio.clearHistory(account)
    return Response('ok\n', mimetype='text/plain')


@bp.route('/retrieve-quotes')
def retrieve_quotes():
    date = Transaction.parseDate(datetime.date.today().isoformat())
    files = Portfolio.get_files(data_dir, 'combined')
    portfolio = Portfolio.combine(init_portfolios(date, files))
    force = request.args.get('force') == 'true'
    retrieveQuotes(portfolio.getCurrentSymbols(), force=force)
    return Response('ok\n', mimetype='text/plain')


@bp.route('/update-quotes')
def update_quotes():
    Portfolio.clearHistory('all')
    storeAllQuotes()
    return Response('ok\n', mimetype='text/plain')


@bp.route('/get-date-quotes')
def get_date_quotes():
    symbols = request.args.get('symbols', '')
    symbols = re.split(r'[, ]', symbols)
    start = request.args.get('start', '1970-01-01')
    end = request.args.get('end', datetime.date.today().isoformat())
    start = datetime.datetime.strptime(start, '%Y-%m-%d').date()
    end = datetime.datetime.strptime(end, '%Y-%m-%d').date()
    quotes = getDateQuotes(symbols, start, end)
    data = [{'date': k, 'quotes': [{'symbol': x[1], 'close': x[2]} for x in g]}
            for k, g in groupby(quotes, key=lambda x: x[0])]
    return jsonify({'data': data})


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


def format_exception():
    type, value, tb = sys.exc_info()
    return {'error': traceback.format_exception(type, value, tb)}


def get_date(date, year):
    if year:
        return year + '-12-31'
    return date if date else datetime.date.today().isoformat()


if __name__ == '__main__':
    # retrieve_quotes()
    skip = None
    # skip = 'options'
    print(get_annual2('ag-broker', skip=skip))
