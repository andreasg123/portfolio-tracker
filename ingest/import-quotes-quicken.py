#!/usr/bin/python3
# -*- coding: utf-8 -*-

import csv
import os
import sys

quote_dir = 'quotes'


def import_quotes(paths):
    os.makedirs(quote_dir, exist_ok=True)
    skip = set([x[:-4] for x in os.listdir(quote_dir) if x.endswith('.csv')])
    for p in paths:
        with open(p) as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) < 3 or not row[0] or len(row[2].split('/')) != 3:
                    continue
                date = parse_date(row[2])
                if date in skip:
                    continue
                symbol = row[0].upper()
                price = row[1]
                with open(os.path.join(quote_dir, date + '.csv'), 'a') as f2:
                    f2.write('%s,%s\n' % (symbol, price))


def parse_date(date):
    values = [int(x) for x in date.split('/')]
    if values[2] < 50:
        values[2] += 2000
    elif values[2] < 1900:
        values[2] += 1900
    return '%04d-%02d-%02d' % (values[2], values[0], values[1])


if __name__ == '__main__':
    import_quotes(sys.argv[1:])
