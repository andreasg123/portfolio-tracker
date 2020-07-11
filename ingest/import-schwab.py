#!/usr/bin/python3
# -*- coding: utf-8 -*-

import csv
import re
import sys


def import_transactions(path):
    with open(path) as f:
        reader = csv.reader(f)
        next(reader)
        next(reader)
        rows = [row for row in reader if row[0] != 'Transactions Total']
    rows.reverse()
    ignore_trades = set(['SWSXX'])
    cash_merger_adj = 0
    merger = None
    reverse_split = None
    for row in rows:
        action = row[1]
        if action == 'Name Change':
            # Name changes aren't informative
            # "06/04/2018","Name Change","QQQ","INVESCO QQQ TRUST","204","","","",
            # "06/04/2018","Name Change","73935A104","POWERSHARES QQQ TRUST NAME CHANGE EFF: 06/04/18","-204","","","",
            continue
        date = parse_date(row[0])
        symbol, is_option = parse_symbol(row[2])
        count = float(row[4]) if row[4] else None
        if is_option:
            count = 100 * count
        price = parse_amount(row[5])
        fee = parse_amount(row[6]) or 0
        amount = parse_amount(row[7])
        if not amount:
            # Older SWSXX dividends (SCHWAB CASH RESERVES SWEEP SHARES)
            amount = count
        # print('#', row)
        if action == 'Cash Merger Adj':
            cash_merger_adj = -count
            continue
        if action in ['Cash Dividend', 'Pr Yr Cash Div', 'Short Term Cap Gain',
                      'Qualified Dividend', 'Non-Qualified Div',
                      'Pr Yr Non-Qual Div']:
            print(date + '|i|' + symbol + '|' + format_amount(amount))
        elif action in ['ADR Mgmt Fee', 'Foreign Tax Paid']:
            print(date + '|i|' + symbol + ' ' + action + '|' +
                  format_amount(amount))
        elif action in ['Bank Interest', 'CRZ Adjustment', 'Interest Adj',
                        'Margin Interest']:
            print(date + '|i|' + action + '|' + format_amount(amount))
        elif action in ['Assigned', 'Expired']:
            # Most of our options are short
            comment = (format_comment('expired; assumed to be short')
                       if action == 'Expired' else '')
            print(date + '|b|' + symbol + '|' + format_amount(count) +
                  '|0|0' + comment)
        elif action in ['Buy', 'Buy to Close', 'Buy to Open',
                        'Sell', 'Sell to Close', 'Sell to Open']:
            if symbol in ignore_trades:
                continue
            action2 = 'b' if action.startswith('Buy') else 's'
            print(date + '|' + action2 + '|' + symbol + '|' +
                  format_amount(count) + '|' + format_amount(price) + '|' +
                  format_amount(fee))
        elif action in ['Journal', 'MoneyLink Transfer', 'Service Fee',
                        'Wire Funds']:
            if action == 'Journal' and symbol == 'SWVXX':
                # These alway show up in balanced pairs and seem to serve
                # no purpose (maybe they indicate margin power)
                print('#', date + '|d|' + row[3] + '|' + format_amount(amount))
            else:
                print(date + '|d|' + row[3] + '|' + format_amount(amount))
        elif action == 'Stock Split':
            print('#', date + '|x|' + symbol + '|??' +
                  format_comment('split; unknown factor'))
        elif action == 'Reverse Split':
            if reverse_split is None:
                reverse_split = count
            else:
                print(date + '|x|' + symbol + '|' +
                      str((count + reverse_split) / -reverse_split) +
                      format_comment('reverse split'))
                reverse_split = None
        elif action == 'Cash Merger':
            price = amount / cash_merger_adj
            price = int(price) if int(price) == price else price
            print(date + '|s|' + symbol + '|' + str(cash_merger_adj) + '|' +
                  str(price) + '|0')
            cash_merger_adj = 0
        elif action == 'Stock Merger':
            if merger is None:
                merger = (symbol, count)
            else:
                print(date + '|c|' + merger[0] + '|' + symbol + '|' +
                      str(-count / merger[1]) +
                      format_comment('merger; check factor for fractional '
                                     'shares'))
                merger = None
        elif action == 'Spin-off':
            print('#', date + '|x|??|' + symbol + '|' + format_amount(count) +
                  ' shares' +
                  format_comment('spin-off; determine source and fraction'))
        elif action == 'Cash In Lieu':
            print('#', date + '|s|' + symbol + '|F|' + format_amount(amount) +
                  '/F|0' + format_comment('cash in lieu; determine fraction F'))
        elif action == 'Security Transfer':
            if count is None:
                print('#', date + '|d|Security Transfer ' + row[3] + '|' +
                      format_amount(amount))
            else:
                action2 = 's' if count < 0 else 'b'
                print('#', date + '|' + action2 + '|' + symbol + '|' +
                      str(abs(count)) + '|0|0' +
                      format_comment('security transfer; add current quote '
                                     'and transaction for (negative) deposit; '
                                     'also check deposits nearby '))
        else:
            print('#', row)
            

def parse_amount(amount):
    if not amount:
        return None
    x = float(amount.replace('$', ''))
    return int(x) if int(x) == x else x


def parse_date(date):
    m = re.match(r'(\d\d/\d\d/\d\d\d\d)(.*)', date)
    if m:
        d = m.group(1)
        g2 = m.group(2)
        if g2.startswith(' as of '):
            d = g2[7:]
        values = d.split('/')
        return '-'.join([values[2], values[0], values[1]])
    return ''


def parse_symbol(symbol):
    m = re.match(r'([A-Z0-9]+) (\d\d/\d\d/\d\d\d\d) ([0-9.]+) ([CP])', symbol)
    if m:
        s = m.group(1)
        d = m.group(2)
        p = m.group(3)
        o = m.group(4)
        p = '%08d' % (float(p) * 1000)
        values = d.split('/')
        return (s + values[2][2:] + values[0] + values[1] + o + p, True)
    else:
        return (symbol, False)


def format_amount(amount):
    return ('%.8f' % amount).rstrip('0').rstrip('.')


def format_comment(comment):
    return '\t# ' + comment


if __name__ == '__main__':
    import_transactions(sys.argv[1])
            
