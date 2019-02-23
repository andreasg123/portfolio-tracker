#!/usr/bin/python3

import csv
from contextlib import closing
import datetime
import io
import json
import gzip
import os
import re
import urllib.request


quote_dir = '/var/www/html/quotes'

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


def getQuotes(d, symbols=None):
    while True:
        # Loop to earlier days until a quote file is found.
        try:
            with open(os.path.join(quote_dir, d.isoformat() + '.csv')) as f:
                return dict((k, float(v)) for k, v in csv.reader(f)
                            if not symbols or k in symbols)
        except FileNotFoundError:
            d -= datetime.timedelta(days=1)


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
    quote_path = os.path.join(quote_dir, datetime.date.today().strftime('%Y-%m-%d.csv'))
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


if __name__ == '__main__':
    # retrieveQuotes(['AAPL', 'HPE'])
    print(getQuotes2(datetime.date.today(), ['AAPL', 'HPE']))
