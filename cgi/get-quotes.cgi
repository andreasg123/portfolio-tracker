#!/usr/bin/python3

import csv
from contextlib import closing
import datetime
import io
import json
import gzip
import os
import re
import string
import sys
import traceback
import urllib.request

from portfolio import Portfolio, Transaction

quote_dir = '/var/www/html/quotes'

spark_url_prefix = 'https://partner-query.finance.yahoo.com/v7/finance/spark?symbols='
spark_url_suffix = '&range=1d&interval=1d&indicators=close&includeTimestamps=false&includePrePost=false&corsDomain=finance.yahoo.com'
csv_url_prefix = 'http://download.finance.yahoo.com/d/quotes.csv?s='
csv_url_suffix = '&f=svhgl1c1t1e&e=.csv'
max_csv_quotes = 20
json_url_prefix = 'https://query1.finance.yahoo.com/v7/finance/quote?lang=en-US&region=US&corsDomain=finance.yahoo.com&fields=symbol,longName,shortName,regularMarketPrice,regularMarketChange,currency,regularMarketTime,regularMarketVolume,quantity,regularMarketDayHigh,regularMarketDayLow,regularMarketOpen,marketCap&symbols='
json_url_suffix = '&formatted=false'
max_json_quotes = 20

quote_headers = [
    ('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; WOW64; rv:53.0) Gecko/20100101 Firefox/53.0'),
    ('Referer', 'https://finance.yahoo.com/'),
    ('Accept-Encoding', 'gzip')
]

spark_quote_paths = [
    ['spark', 'result', 0, 'symbol'],
    ['spark', 'result', 0, 'response', 0, 'indicators', 'unadjquote', 0, 'unadjhigh', 0],
    ['spark', 'result', 0, 'response', 0, 'indicators', 'unadjquote', 0, 'unadjlow', 0],
    ['spark', 'result', 0, 'response', 0, 'indicators', 'quote', 0, 'close', 0],
    ['spark', 'result', 0, 'response', 0, 'timestamp', 0]
]

json_quote_fields = [
    'symbol',
    'regularMarketDayHigh',
    'regularMarketDayLow',
    'regularMarketPrice',
    'regularMarketTime'
]

def extractSparkQuote(f):
    data = json.load(f)
    #print(data)
    f.close()
    quote = []
    for p in spark_quote_paths:
        try:
            d = data
            for i in p:
                #print(i, d)
                d = d[i]
            #print('append', d)
            quote.append(d)
        except KeyError:
            quote.append(None)
    #print(quote)
    return quote

def extractJsonQuotes(f):
    data = json.load(f)
    #print(data)
    f.close()
    return [[q.get(n, 0.0) for n in json_quote_fields]
            for q in data['quoteResponse']['result']]

def createRequest(url):
    #print('createRequest', url)
    req = urllib.request.Request(url, None)
    for h in quote_headers:
        req.add_header(h[0], h[1])
    return req

def getRequest(req):
    f = urllib.request.urlopen(req, None, 60)
    if f.info().get('Content-Encoding') == 'gzip':
        buf = io.BytesIO(f.read())
        f.close()
        f = gzip.GzipFile(fileobj=buf)
    return f

def getSparkQuote(sym):
    #print('getSparkQuote', sym)
    try:
        return extractSparkQuote(getRequest(createRequest(spark_url_prefix + sym + spark_url_suffix)))
    except urllib.request.HTTPError as e:
        if e.code == 404:
            print('Unknown symbol', sym)
            return None
        else:
            raise

def getCsvQuotes(symbols):
    quotes = []
    while symbols:
        if len(symbols) == max_csv_quotes + 1:
            s = symbols[:max_csv_quotes-1]
            symbols = symbols[max_csv_quotes-1:]
        elif len(symbols) > max_csv_quotes:
            s = symbols[:max_csv_quotes]
            symbols = symbols[max_csv_quotes:]
        else:
            s = symbols
            symbols = []
        with closing(getRequest(createRequest(csv_url_prefix + ','.join(s) + csv_url_suffix))) as f:
            quotes += csv.reader(f)
    return quotes

def getJsonQuotes(symbols):
    quotes = []
    while symbols:
        if len(symbols) == max_csv_quotes + 1:
            s = symbols[:max_csv_quotes-1]
            symbols = symbols[max_csv_quotes-1:]
        elif len(symbols) > max_csv_quotes:
            s = symbols[:max_csv_quotes]
            symbols = symbols[max_csv_quotes:]
        else:
            s = symbols
            symbols = []
        with closing(getRequest(createRequest(json_url_prefix + ','.join(s) + json_url_suffix))) as f:
            quotes += extractJsonQuotes(f)
    return quotes

def formatPrice(amount):
    try:
        s = '%9.3f' % amount
        if s[-1] == '0':
            s = s[:-1] + ' '
        return s
    except TypeError:
        return '-   '

def getQuotes(symbols):
    quote_path = os.path.join(quote_dir, datetime.date.today().strftime('%y-%m-%d.txt'))
    if os.path.exists(quote_path):
        #print('exists', quote_path)
        exit(0)

    stocks = []
    options = []
    today = datetime.date.today().strftime('%y%m%d')
    option_pat = re.compile('^([^0-9]+)([0-9]+)[CP]([0-9]+)$')
    filtered_symbols = []
    for arg in symbols:
        if len(arg) < 16:
            filtered_symbols.append(arg)
        else:
            m = option_pat.match(arg)
            if m and len(m.group(3)) == 8 and len(m.group(2)) == 6 and m.group(2) >= today:
                # proper syntax and expiration
                filtered_symbols.append(arg)
    symbols = filtered_symbols
    quotes = getJsonQuotes(symbols)
    retrieved = set([q[0] for q in quotes])
    symbols = [s for s in symbols if s not in retrieved]
    try:
        for o in symbols:
            q = getSparkQuote(o)
            if q:
                quotes.append(q)
    except:
        traceback.print_exc()
        exit(0)

    quotes.sort(key=lambda x: x[0])
    with open(quote_path, 'w') as f:
        f.write('Ticker                Vol     High       Low      Last    Change   Update\n')
        f.write('------                ---     ----       ---      ----    ------   ------\n')
        for q in quotes:
            vol = 0
            last = 0
            low = 0
            high = 0
            change = 0
            update = ''
            sym = q[0]
            if len(q) == 5:
                high = q[1]
                low = q[2]
                last = q[3]
                update = str(q[4])
            else:
                if q[2] == 'N/A' or q[4] == 'N/A':
                    continue
                vol = int(q[1]) / 100
                high = float(q[2])
                low = float(q[3])
                last = float(q[4])
                change = float(q[5])
                update = q[6]
            #print(sym, last)
            if not last:
                continue
            if len(sym) >= 16:
                prefix = '%-23s 0' % sym
            else:
                prefix = '%-17s%8d' % (sym, vol)
            f.write('%s %9s %9s %9s %9s  %s\n' % (prefix, formatPrice(high), formatPrice(low), formatPrice(last), formatPrice(change), update))

sys.stdout.write('Content-type: text/plain\n')
sys.stdout.write('\n')
sys.stdout.flush()

date = Transaction.parseDate(datetime.date.today().isoformat())
portfolio = Portfolio(date)
files = Transaction.getAccounts()
all_buckets = []
for f in files:
    portfolio.account = f
    t = Transaction.readTransactions(os.path.join('data', f), date)
    portfolio.fillBuckets(t)
    all_buckets.append(portfolio.buckets)
    portfolio.emptyBuckets()
portfolio.combineBuckets(all_buckets)
getQuotes(portfolio.getCurrentSymbols())
sys.stdout.write('ok\n')
