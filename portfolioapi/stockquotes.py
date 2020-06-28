#!/usr/bin/python3
# -*- coding: utf-8 -*-

import bisect
import csv
from contextlib import closing
import datetime
import io
import json
import gzip
import sqlite3
import os
import re
import urllib.request


quote_dir = '/var/www/html/quotes'
quote_db = '/var/www/portfolioapi/cache/quotes.db'

json_url_prefix = 'https://query1.finance.yahoo.com/v7/finance/quote?lang=en-US&region=US&corsDomain=finance.yahoo.com&fields=symbol,longName,shortName,regularMarketPrice,regularMarketChange,currency,regularMarketTime,regularMarketVolume,quantity,regularMarketDayHigh,regularMarketDayLow,regularMarketOpen,marketCap&symbols='
json_url_suffix = '&formatted=false'
max_json_quotes = 20

quote_headers = [
    ('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; WOW64; rv:53.0) Gecko/20100101 Firefox/53.0'),
    ('Referer', 'https://finance.yahoo.com/'),
    ('Accept-Encoding', 'gzip')
]


json_quote_fields = [
    'symbol',
    'regularMarketPrice'
]


def parseQuote(s):
    if len(s) < 55 or s.startswith('Ticker') or s.startswith('------'):
        return None
    val = s.split()
    if len(val) > 4:
        return (val[0], float(val[4]))


def getQuotesOld(d, symbols=None):
    while True:
        # Loop to earlier days until a quote file is found.
        try:
            with open(os.path.join(
                    quote_dir, d.isoformat()[2:] + '.txt')) as f:
                return dict([q for q in (parseQuote(s) for s in f)
                             if q is not None and
                             (not symbols or q[0] in symbols)])
        except FileNotFoundError:
            d -= datetime.timedelta(days=1)


def getFileQuotes(d, symbols=None):
    # Loop to earlier days until a quote file is found.
    names = sorted([x for x in os.listdir(quote_dir) if x.endswith('.csv')])
    idx = bisect.bisect_right(names, d.isoformat() + '.csv')
    if idx == 0:
        return {}
    with open(os.path.join(quote_dir, names[idx - 1])) as f:
        return dict((k, float(v)) for k, v in csv.reader(f)
                    if not symbols or k in symbols)


def getFileQuoteDates(start, end):
    names = sorted([x for x in os.listdir(quote_dir) if x.endswith('.csv')])
    idx1 = bisect.bisect_left(names, start.isoformat() + '.csv')
    idx2 = bisect.bisect_right(names, end.isoformat() + '.csv')
    return [datetime.datetime.strptime(x[:-4], '%Y-%m-%d').date()
            for x in names[idx1:idx2]]


def createRequest(url):
    #print('createRequest', url)
    req = urllib.request.Request(url, None)
    for h in quote_headers:
        req.add_header(h[0], h[1])
    return req


def openRequest(req):
    f = urllib.request.urlopen(req, None, 60)
    if f.info().get('Content-Encoding') == 'gzip':
        buf = io.BytesIO(f.read())
        f.close()
        f = gzip.GzipFile(fileobj=buf)
    return f


def extractJsonQuotes(f):
    data = json.load(f)
    #print(data)
    f.close()
    return [[q.get(n, 0.0) for n in json_quote_fields]
            for q in data['quoteResponse']['result']]


def retrieveJsonQuotes(symbols):
    quotes = []
    while symbols:
        if len(symbols) == max_json_quotes + 1:
            s = symbols[:max_json_quotes-1]
            symbols = symbols[max_json_quotes-1:]
        elif len(symbols) > max_json_quotes:
            s = symbols[:max_json_quotes]
            symbols = symbols[max_json_quotes:]
        else:
            s = symbols
            symbols = []
        with closing(openRequest(createRequest(
                json_url_prefix + ','.join(s) + json_url_suffix))) as f:
            quotes += extractJsonQuotes(f)
    return quotes


def retrieveQuotes(symbols, force=False):
    ds = datetime.date.today().isoformat()
    quote_path = os.path.join(quote_dir, '{0}.csv'.format(ds))
    if not force and os.path.exists(quote_path):
        return
    stocks = []
    options = []
    today = datetime.date.today().strftime('%y%m%d')
    option_pat = re.compile(r'(.*)(\d{6})([PC])(\d{8})')
    filtered_symbols = []
    for arg in symbols:
        if len(arg) < 16:
            filtered_symbols.append(arg)
        else:
            m = option_pat.fullmatch(arg)
            if m and m.group(2) >= today:
                # proper syntax and expiration
                filtered_symbols.append(arg)
    quotes = retrieveJsonQuotes(filtered_symbols)
    quotes.sort(key=lambda x: x[0])
    with open(quote_path, 'w') as f:
        writer = csv.writer(f)
        for q in quotes:
            writer.writerow(q)
    if quotes:
        try:
            c = getQuoteCursor(quote_db)
            c.execute('DELETE FROM quotes WHERE date=?', [ds])
            c.executemany('INSERT INTO quotes(date,symbol,quote) VALUES(?,?,?)',
                          [(ds, k, v) for k, v in quotes])
            c.connection.commit()
        finally:
            c.connection.close()


def getQuoteCursor(name):
    os.makedirs(os.path.dirname(name), exist_ok=True)
    conn = sqlite3.connect(name)
    return conn.cursor()


def createQuoteTable(cursor):
    cursor.execute('CREATE TABLE IF NOT EXISTS quotes ('
                   'date TEXT, symbol TEXT, quote NUMBER,'
                   'PRIMARY KEY (date, symbol))')


def storeAllQuotes():
    c = getQuoteCursor(quote_db)
    try:
        createQuoteTable(c)
        quote_dates = getFileQuoteDates(datetime.date(1990, 1, 1),
                                        datetime.date.today())
        c.execute('DELETE FROM quotes')
        for d in quote_dates:
            ds = d.isoformat()
            quotes = getFileQuotes(d)
            c.executemany('INSERT INTO quotes(date,symbol,quote) '
                          'VALUES(?,?,?)',
                          [(ds, k, v) for k, v in quotes.items()])
        c.connection.commit()
    finally:
        c.connection.close()


def getQuotes(d, symbols=None):
    c = getQuoteCursor(quote_db)
    try:
        createQuoteTable(c)
        c.execute('SELECT MAX(date) FROM quotes WHERE date<=?',
                  [d.isoformat()])
        row = c.fetchone()
        if row is None:
            return {}
        if symbols:
            # Handle set
            symbols = list(symbols)
            c.execute('SELECT symbol,quote FROM quotes '
                      'WHERE date=? AND symbol IN ({0})'
                      .format(','.join(['?'] * len(symbols))),
                      [row[0]] + symbols)
        else:
            c.execute('SELECT symbol,quote FROM quotes WHERE date=?', [row[0]])
        return dict(c.fetchall())
    finally:
        c.connection.close()


def getQuoteDates(start, end):
    c = getQuoteCursor(quote_db)
    try:
        c.execute('SELECT DISTINCT date FROM quotes WHERE date>=? AND date<=? '
                  'ORDER BY date',
                  [start.isoformat(), end.isoformat()])
        return [datetime.datetime.strptime(x[0], '%Y-%m-%d').date()
                for x in c.fetchall()]
    finally:
        c.connection.close()


def setQuotePaths(dir_path, db_path):
    global quote_dir, quote_db
    quote_dir = dir_path
    quote_db = db_path


def main():
    # retrieveQuotes(['AAPL', 'HPE'])
    # print(getQuotes2(datetime.date.today(), ['AAPL', 'HPE']))
    storeAllQuotes()
    # print(getQuoteDates(datetime.date(2020, 2, 3), datetime.date(2020, 2, 10)))
    # print(getQuotes(datetime.date(2020, 2, 9), ['AAPL', 'SPY', 'VOO']))


if __name__ == '__main__':
    main()
