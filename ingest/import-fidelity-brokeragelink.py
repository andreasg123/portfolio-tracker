#!/usr/bin/python3
# -*- coding: utf-8 -*-

import csv
import sys


fund_symbols = {
    '73935A104': 'QQQ'
}


def import_transactions(paths):
    rows = []
    for p in paths:
        with open(p) as f:
            reader = csv.reader(f)
            x = [[col.strip() for col in row] for row in reader
                 if len(row) > 10 and len(row[0].split('/')) == 3]
            x.reverse()
            rows += x
    for row in rows:
        date = parse_date(row[0])
        action = row[1]
        symbol = fund_symbols.get(row[2], row[2])
        count = parse_amount(row[5])
        price = parse_amount(row[6])
        fee1 = parse_amount(row[7])
        fee2 = parse_amount(row[8])
        interest = parse_amount(row[9])
        amount = parse_amount(row[10])
        if action.startswith('DIVIDEND RECEIVED'):
            print(date + '|i|' + symbol + '|' + format_amount(amount))
        elif action.startswith('NAME CHANGED'):
            # This only happened for QQQ and wasn't very useful
            pass
        elif action.startswith('TRANSFERRED'):
            print(date + '|d|Transfer|' + format_amount(amount))
        elif (action.startswith('YOU BOUGHT') or
              action.startswith('REINVESTMENT')):
            if symbol != 'FDRXX':
                # Buying and selling of FDRXX isn't listed
                print(date + '|b|' + symbol + '|' + format_amount(count) +
                      '|' + format_amount(price) + '|' +
                      format_amount(fee1 + fee2))
        elif (action.startswith('YOU SOLD') or
              action.startswith('IN LIEU OF FRX SHARE')):
            print(date + '|s|' + symbol + '|' + format_amount(abs(count)) +
                  '|' + format_amount(price) + '|' +
                  format_amount(fee1 + fee2))
        else:
            print('#', row)


def parse_amount(amount):
    return float(amount) if amount else 0


def parse_date(date):
    values = date.split('/')
    return '-'.join([values[2], values[0], values[1]])


def format_amount(amount):
    return ('%.8f' % amount).rstrip('0').rstrip('.')


if __name__ == '__main__':
    import_transactions(sys.argv[1:])
