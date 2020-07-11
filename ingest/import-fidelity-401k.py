#!/usr/bin/python3
# -*- coding: utf-8 -*-

import csv
import math
import re
import sys

fee_as_negative_dividend = True
fund_symbols = {
    # FXPAL
    'CAUSEWAY EM MKTS IS': 'CEMIX',
    'FID 500 INDEX': 'FXAIX',
    'FID 500 INDEX PR': 'FUSVX',
    'FID CAPITAL &amp; INCOME': 'FAGIX',
    'FID CONTRAFUND': 'FCNTX',
    'FID EMERGING MKTS': 'FEMKX',
    'FID EXTD MKT IDX': 'FSMAX',
    'FID GOVT MMRK PRM': 'FZCXX',
    'FID INTL DISCOVERY': 'FIGRX',
    'FID LEVERGD CO STK': 'FLVCX',
    'FID SEL NATURAL RES': 'FNARX',
    'FID SEL TECHNOLOGY': 'FSPTX',
    'MFS MID CAP VALUE R6': 'MVCKX',
    'PIF SMALL CAP INST': 'PSLIX',
    'PIF SMALL CAP R5': 'PSBPX',
    'TRP RETIREMENT 2025': 'TRRHX',
    'VRS PARTNERS A': 'RSPFX',
    'VS EMERGING MKTS A': 'GBEMX',
    'WF EMRG MKTS EQ ADM': 'EMGYX',
    # Uber
    'FID CONTRAFUND K6': 'FLCNX',
    'FID MID CAP IDX': 'FSMDX',
    'FID MID CAP IDX PR': 'FSCKX',
    'FID SM CAP IDX': 'FSSNX',
    'FID SM CAP IDX PR': 'FSSVX',
    # IBM
    # "IBM STOCK" is NOT regular shares of IBM as the share price is
    # completely different.
    # https://workplaceservices.fidelity.com/mybenefits/workplacefunds/summary/OJFK
    # 'LARGE COMPANY IDX': 'OJFK',
    # 'SMALL/MID-CAP IDX': 'OJFN',
    # 'TOTAL BOND MARKET': 'OJFC',
    'PIM RE REAL RET INST': 'PRRSX',
    # Microsoft
    # 'INTL GROWTH ACCOUNT': 'TPC6',
    # 'PIMCO TOTAL RETURN': 'TPG6'
    # 'VANG RUS 1000 GR TR': 'OAMO',
    # 'VANG RUS 2000 GR TR': 'OAMQ',
    'MSFT COMMON STOCK': 'MSFT',
    'VANG GRTH INDEX INST': 'VIGIX',
    'VANG SM GR IDX INST': 'VSGIX',
}


def import_transactions(path):
    with open(path) as f:
        reader = csv.reader(f)
        rows = [row for row in reader
                if len(row) >= 5 and len(row[0].split('/')) == 3]
    rows.reverse()
    for row in rows:
        action = row[2]
        if action == 'Transfer':
            # Transfers are between sources, e.g., after-tax to Roth
            continue
        date = parse_date(row[0])
        symbol = fund_symbols.get(row[1], row[1])
        amount = parse_amount(row[3])
        count = parse_amount(row[4])
        price = amount / count if count != 0 else 0
        if action in ['Balance Forward', 'Conversion Balance']:
            print(date + '|d|' + symbol + '|' + format_amount(amount) +
                  format_comment('balance forward'))
            print(date + '|b|' + symbol + '|' + format_amount(count) + '|' +
                  format_amount(price) + '|0')
        elif action == 'Exchanges':
            if symbol == 'BROKERAGELINK':
                print(date + '|d|BROKERAGELINK|' + format_amount(-amount))
            else:
                action2 = 's' if amount < 0 else 'b'
                print(date + '|' + action2 + '|' + symbol + '|' +
                      format_amount(abs(count)) + '|' + format_amount(price) +
                      '|0' + format_comment('exchange'))
        elif action in ['Exchange In', 'Exchange Out', 'Exchange out']:
            action2 = 'b' if action == 'Exchange In' else 's'
            print(date + '|' + action2 + '|' + symbol + '|' +
                  format_amount(abs(count)) + '|' + format_amount(price) +
                  '|0' + format_comment('exchange'))
        elif action in ['Interest', 'Dividends', 'DIVIDEND', 'REVENUE CREDIT',
                        'Transfers']:
            # It's not really clear what "Transfers" means in the Microsoft
            # 401k but it acts like a negative dividend.
            # 09/10/2015,MSFT COMMON STOCK,Transfers,"-142.60","-3.325"
            # 09/10/2015,MSFT COMMON STOCK,Dividends,"142.60","3.325"
            if amount == 0 and count < 0:
                # reverse split:
                # 08/07/2015,PIM RE REAL RET INST,DIVIDEND,"0.00","-6,849.622"
                print(date + '|x|' + symbol + '|-0.5' +
                      format_comment('reverse split'))
            else:
                action2 = 's' if count < 0 else 'b'
                print(date + '|i|' + symbol + '|' + format_amount(amount))
                print(date + '|' + action2 + '|' + symbol + '|' +
                      format_amount(abs(count)) + '|' + format_amount(price) +
                      '|0')
        elif action in ['CONTRIBUTION', 'Withdrawals', 'Adjustments',
                        'ADMINISTRATIVE FEES', 'RECORDKEEPING FEE',
                        'REAL TIME TRADE COMMISSION',
                        'ESOP CASH DIV.- CHECK FEE']:
            if count == 0:
                count = math.copysign(0.0001, amount)
                price = amount / count
            comment = ('contribution' if action == 'CONTRIBUTION'
                       else 'withdrawal' if action == 'Withdrawals'
                       else 'adjustment' if action == 'Adjustments'
                       else 'fee')
            action2 = 's' if count < 0 else 'b'
            action3 = ('i' if fee_as_negative_dividend and
                       action in ['ADMINISTRATIVE FEES', 'RECORDKEEPING FEE',
                                  'REAL TIME TRADE COMMISSION',
                                  'ESOP CASH DIV.- CHECK FEE']
                       else 'd')
            print(date + '|' + action3 + '|' + symbol + '|' + format_amount(amount))
            print(date + '|' + action2 + '|' + symbol + '|' +
                  format_amount(abs(count)) + '|' +
                  format_amount(abs(price)) + '|0' + format_comment(comment))
        elif action in ['REALIZED G/L', 'Change in Market Value',
                        'Change on Market Value']:
            pass
        else:
            print('#', date, symbol, action, amount, count)
    # print(sorted(set([row[2] for row in rows])))


def parse_amount(amount):
    return float(amount.replace(',', ''))


def parse_date(date):
    values = date.split('/')
    return '-'.join([values[2], values[0], values[1]])


def format_amount(amount):
    return ('%.8f' % amount).rstrip('0').rstrip('.')


def format_comment(comment):
    return '\t# ' + comment


# ['Adjustments', 'Balance Forward', 'CONTRIBUTION', 'DIVIDEND', 'Exchanges', 'Interest', 'REALIZED G/L', 'Transfer']

if __name__ == '__main__':
    import_transactions(sys.argv[1])
