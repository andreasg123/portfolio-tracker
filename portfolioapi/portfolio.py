#!/usr/bin/python3
# -*- coding: utf-8 -*-

from collections import defaultdict
import copy
import datetime
from functools import reduce
from itertools import groupby
import json
import math
import os
import re
import sqlite3
import sys

from .stockquotes import getQuotes, getQuoteDates

EPOCH = datetime.date(1970, 1, 1)
LONG_DAYS = 365
cash_like = set(['SWVXX'])
data_dir = '/var/www/html/portfolio/data'
cache_dir = '/var/www/portfolioapi/cache'


def makeDict(obj, keys):
    return {k: round(v, 8) if isinstance(v, float) else v
            for k, v in ((k, getattr(obj, k, None)) for k in keys)
            if v is not None}

class Dividend:
    def __init__(self, date, amount):
        self.date = date
        self.amount = amount

    def __str__(self):
        return '%d|%.2f' % (self.date, self.amount)

    def toDict(self):
        data = {'date': Transaction.toDate(self.date).isoformat()}
        data.update(makeDict(self, ['amount']))
        return data


class Interest:
    def __init__(self, name, amount):
        self.name = name
        self.amount = amount


class Lot:
    def __init__(self, symbol, nshares, share_price, share_expense, share_adj,
                 purchase_date):
        self.symbol = symbol
        # can be negative for short sales
        self.nshares = nshares
        self.share_price = share_price
        # expense = abs(nshares) * share_expense
        self.share_expense = share_expense
        self.purchase_date = purchase_date
        # adjustment of the share price due to options
        self.share_adj = share_adj
        # Additional holding days due to wash sale
        self.wash_days = 0
        self.dividends = []
        self.return_of_capital = []

    def __str__(self):
        return ('%s|%.3f|%.2f|%.5f|%d|%.5f' %
                (self.symbol, self.nshares, self.share_price,
                 self.share_expense, self.purchase_date, self.share_adj))

    def toDict(self):
        data = makeDict(self, ['symbol', 'nshares', 'share_price',
                               'share_expense', 'share_adj', 'wash_days',
                               'account'])
        for k in ['dividends', 'return_of_capital']:
            v = getattr(self, k)
            if v:
                data[k] = [x.toDict() for x in v]
        data['purchase_date'] = Transaction.toDate(self.purchase_date).isoformat()
        return data


class CompletedLot:
    def __init__(self, lot, end_date, nshares, end_share_price,
                 end_share_expense, end_share_adj):
        self.symbol = lot.symbol
        self.start_date = lot.purchase_date
        self.end_date = end_date
        self.nshares = nshares
        self.start_share_price = lot.share_price
        self.end_share_price = end_share_price
        self.start_share_expense = lot.share_expense
        self.end_share_expense = end_share_expense
        self.start_share_adj = lot.share_adj
        self.end_share_adj = end_share_adj
        self.wash_days = lot.wash_days
        self.wash_sale = 0
        # Always copy the dividends because they will be adjusted to 0 after
        # the transaction.
        self.dividends = [Dividend(d.date,
                                   d.amount * nshares / lot.nshares)
                          for d in lot.dividends]
        account = getattr(lot, 'account', None)
        if account is not None:
            self.account = account

    def __str__(self):
        return ('%s|%.3f|%.2f|%.2f|%.5f|%.5f|%.5f|%.5f|%d|%d|%.5f' %
                (self.symbol, self.nshares, self.start_share_price,
                 self.end_share_price, self.start_share_expense,
                 self.end_share_expense, self.start_share_adj,
                 self.end_share_adj, self.start_date, self.end_date,
                 self.wash_sale))

    def getGain(self):
        return (round(self.nshares *
                      (self.end_share_price - self.start_share_price), 2) -
                round(abs(self.nshares) *
                      (self.start_share_expense + self.start_share_adj +
                       self.end_share_expense + self.end_share_adj), 2))

    def toDict(self):
        # Don't include dividends because they are only needed to facilitate
        # wash sales.
        data = makeDict(
            self, ['symbol', 'nshares', 'start_share_price', 'end_share_price',
                   'start_share_expense', 'end_share_expense',
                   'start_share_adj', 'end_share_adj', 'wash_sale', 'wash_days',
                   'account'])
        for k in ['start_date', 'end_date']:
            v = getattr(self, k)
            if v:
                data[k] = Transaction.toDate(v).isoformat()
        return data


class Transaction:
    def __init__(self, date, action_type, name):
        self.date = date
        self.type = action_type.lower()
        self.name = name
        self.name2 = ''
        self.count = 0
        self.amount1 = 0
        self.amount2 = 0

    def __str__(self):
        return ('%d|%s|%s|%s|%.3f|%.2f|%.2f' %
                (self.date, self.type, self.name, self.name2, self.count,
                 self.amount1, self.amount2))

    def is_cash_like(self):
        return self.name in cash_like

    @staticmethod
    def fromDate(d):
        # Internals dates are represented as the number of days since the epoch.
        return (d - EPOCH).days

    @staticmethod
    def toDate(days):
        return EPOCH + datetime.timedelta(days=days)

    @staticmethod
    def parseDate(val):
        val = [int(x) for x in val.split('-')]
        y = val[0]
        if y < 100:
            y += 2000 if y < 70 else 1900
        return Transaction.fromDate(datetime.date(y, val[1], val[2]))

    @staticmethod
    def fromYear(year):
        return Transaction.fromDate(datetime.date(year, 1, 1))

    @staticmethod
    def fromYearEnd(year):
        return Transaction.fromDate(datetime.date(year, 12, 31))

    @staticmethod
    def toYear(days):
        return Transaction.toDate(days).year

    @staticmethod
    def today():
        return Transaction.fromDate(datetime.date.today())

    @staticmethod
    def yearBegin(date):
        d = Transaction.toDate(date)
        return Transaction.fromDate(d.replace(month=1, day=1))

    @staticmethod
    def parse(line):
        # Using find instead of the first split takes the same total time.
        val = line.split('#', 1)[0].rstrip().split('|')
        if len(val) < 3:
            return None
        t = Transaction(Transaction.parseDate(val[0]), val[1], val[2])
        if t.type == 'd' or t.type == 'i' or t.type == 'r' or t.type == 'x':
            # deposit, interest, return-of-capital, split
            t.amount1 = float(val[3])
            t.name2 = val[4] if len(val) > 4 else val[2]
            t.amount2 = float(val[5]) if len(val) > 5 else 1
        elif t.type == 'b' or t.type == 's':
            # buy, sell
            t.count = float(val[3])
            t.amount1 = float(val[4]) if len(val) > 4 else 0
            t.amount2 = float(val[5]) if len(val) > 5 else 0
        elif t.type == 'c':
            # change
            t.name2 = val[3]
            t.count = float(val[4]) if len(val) > 4 else 1
            if len(val) > 6:
                # cash per share
                t.amount1 = float(val[5])
                # fraction of transaction paid in cash
                t.amount2 = float(val[6])
        return t

    @staticmethod
    def getAccounts(path='data'):
        files = []
        with os.scandir(path) as it:
            for entry in it:
                n = entry.name
                if (n != 'transfers' and not n.startswith('.') and
                    not n.endswith('~') and entry.is_file()):
                    files.append(n)
        files.sort()
        return files

    @staticmethod
    def readTransactions(filename, date=None, skip=None):
        skip_options = skip == 'options'
        with open(filename, encoding='utf-8') as f:
            try:
                transactions = Transaction.read(f, date)
            except Exception as e:
                raise type(e)(str(e) + ' ' + filename)
        # transactions.sort(key=lambda t: t.date)
        if skip_options:
            transactions2 = []
            for k, g in groupby(transactions, lambda t: t.date):
                group = Portfolio.matchOptions(list(g))
                for t in group:
                    if isinstance(t, tuple):
                        # print(Transaction.toDate(k), t[0], t[1])
                        q = getQuotes(Transaction.toDate(k), set([t[0].name]))
                        t[0].amount1 = q.get(t[0].name, 0)
                        transactions2.append(t[0])
                    elif not isOptionSymbol(t.name):
                        # if t.name == 'MA':
                        #     print(Transaction.toDate(k), t)
                        transactions2.append(t)
            transactions = transactions2
            # for t in transactions:
            #     print(Transaction.toDate(t.date).isoformat(), t)
        return transactions

    @staticmethod
    def read(file, date=None):
        if date is None:
            date = Transaction.today()
        transactions = []
        for x in file:
            t = Transaction.parse(x)
            if t is None:
                continue
            if t.date > date:
                break
            transactions.append(t)
        return transactions

    @staticmethod
    def checkTransactions(filename):
        prev = 0
        with open(filename, encoding='utf-8') as f:
            for idx, x in enumerate(f):
                t = Transaction.parse(x)
                if t is not None:
                    if t.date < prev:
                        sys.stdout.write(str(idx + 1) + ' ' + x)
                    prev = t.date

    @staticmethod
    def checkOptions(filename):
        transactions = Transaction.readTransactions(filename)
        sales = defaultdict(list)
        for t in transactions:
            if ((t.type == 's' or t.type == 'b') and
                not t.is_cash_like() and not isOptionSymbol(t.name)):
                sales[t.name].append(t)
        for t in transactions:
            if (t.type == 's' or t.type == 'b') and t.amount1 == 0:
                opt = getOptionParameters(t.name)
                if not opt[0]:
                    continue
                for t2 in sales[opt[0]]:
                    if (t2.date != t.date and abs(t2.date - t.date) < 7 and
                        t2.amount1 == opt[3] and
                        (t2.type == t.type) == (opt[2] == 'P')):
                        print('option', Transaction.toDate(t.date).isoformat(), str(t), ' ', str(t2))


def adjustDividends(dividends, factor):
    for d in dividends:
        d.amount *= factor


def isOptionSymbol(symbol):
    return (len(symbol) >= 16 and (symbol[-9] == 'P' or symbol[-9] == 'C') and
            symbol[-8:].isdigit() and symbol[-15:-9].isdigit())


def getOptionParameters(symbol):
    m = re.fullmatch(r'(.*)(\d{6})([PC])(\d{8})', symbol)
    if not m:
        return (None, None, None, None)
    else:
        sym = m.group(1)
        if sym == 'BRKB':
            sym = 'BRK-B'
        elif sym == 'VIX':
            sym = '^VIX'
        date = m.group(2)
        date = date[:2] + '-' + date[2:4] + '-' + date[4:]
        return (sym, Transaction.parseDate(date), m.group(3),
                0.001 * float(m.group(4)))


def getOptionPair(symbol):
    opt = getOptionParameters(symbol)
    return (symbol,) if not opt[0] else (symbol, opt[0])


class Portfolio:
    account_transfers = []

    def __init__(self, date, account=None):
        self.portfolio_date = date
        self.account = account
        self.bg_year = Transaction.yearBegin(date)
        self.first_deposit = self.bg_year + 366
        self.lots = defaultdict(list)
        self.completed_lots = []
        self.assigned_lots = []
        self.interest = []
        self.realized_long = 0
        self.realized_short = 0
        self.purchase_total = 0
        self.interest_total = 0
        self.cash = 0
        self.cash_diff = 0
        self.cash_like = 0
        self.cash_like_diff = 0
        self.equity_diff = 0
        self.new_deposits = 0
        self.total_deposits = 0
        self.year_dividend = defaultdict(lambda: defaultdict(float))
        self.deposits = []
        # Track wash sales
        # Lot
        self.recent_buys = []
        # CompletedLot
        self.recent_sells = []

    def emptyDeposits(self):
        self.deposits = []

    def sortDeposits(self):
        self.deposits.sort(key=lambda x: x[0])

    def emptyLots(self):
        self.lots = defaultdict(list)

    def sortLots(self):
        for v in self.lots.values():
            v.sort(key=lambda x: x.purchase_date)
        key=lambda x: (x.end_date, x.start_date);
        self.completed_lots.sort(key=key)
        self.assigned_lots.sort(key=key)

    # def combineLots(self, all_lots):
    #     keys = sorted(set([k for al in all_lots for k in al]))
    #     self.lots = {k: [lt for al in all_lots for lt in al.get(k, [])]
    #                  for k in keys}

    def createLot(self, symbol, nshares, share_price, share_expense,
                  share_adj, purchase_date):
        lt = Lot(symbol, nshares, share_price, share_expense, share_adj,
                 purchase_date)
        if self.account is not None:
            lt.account = self.account
        return lt

    def splitLot(self, lt, nshares):
        factor = nshares / lt.nshares
        lt2 = copy.deepcopy(lt)
        adjustDividends(lt2.dividends, 1 - factor)
        adjustDividends(lt2.return_of_capital, 1 - factor)
        adjustDividends(lt.dividends, factor)
        adjustDividends(lt.return_of_capital, factor)
        lt2.nshares = lt.nshares - nshares
        lt.nshares = nshares
        lots = self.lots[lt.symbol]
        # if lt.symbol == 'AAPL120317C00540000':
        #     print('splitLot', lt, lots)
        try:
            lots.insert(lots.index(lt), lt2)
        except ValueError:
            print('error', str(lt), [str(x) for x in lots])
        return (lt2, lt)

    def splitCompletedLot(self, clt, nshares):
        factor = nshares / clt.nshares
        clt2 = copy.deepcopy(clt)
        # CompletedLot doesn't have return_of_capital
        adjustDividends(clt2.dividends, 1 - factor)
        adjustDividends(clt.dividends, factor)
        clt2.nshares = clt.nshares - nshares
        clt.nshares = nshares
        self.completed_lots.insert(self.completed_lots.index(clt) + 1, clt2)
        return clt2

    def sellLot(self, lt, sold_shares, share_price, share_expense, share_adj,
                share_proceeds, date):
        current_shares = sold_shares
        if lt.nshares <= 0:
            return (0, sold_shares)
        if current_shares > lt.nshares:
            current_shares = lt.nshares
        sold_shares -= current_shares
        factor = (lt.nshares - current_shares) / lt.nshares
        basis = current_shares * (lt.share_price + lt.share_expense)
        clt = CompletedLot(lt, date, current_shares, share_price,
                           share_expense, share_adj)
        self.completed_lots.append(clt)
        self.recent_sells.append(clt)
        lt.nshares -= current_shares
        if lt.nshares < 0.0001:
            lt.nshares = 0
        adjustDividends(lt.dividends, factor)
        adjustDividends(lt.return_of_capital, factor)
        self.purchase_total += basis
        if date >= self.bg_year:
            realized = share_proceeds * current_shares - basis
            if date - lt.purchase_date >= LONG_DAYS:
                self.realized_long += realized
            else:
                self.realized_short += realized
        return (basis, sold_shares)

    def buyLot(self, lt, bought_shares, share_price, share_expense,
               share_adj, date):
        current_shares = bought_shares
        if lt.nshares >= 0:
            return (0, bought_shares)
        if current_shares > -lt.nshares:
            current_shares = -lt.nshares
        bought_shares -= current_shares
        basis = current_shares * (lt.share_price + lt.share_expense)
        clt = CompletedLot(lt, date, -current_shares, share_price,
                           share_expense, share_adj)
        self.completed_lots.append(clt)
        lt.nshares += current_shares
        if lt.nshares > -0.0001:
            lt.nshares = 0
        return (basis, bought_shares)

    def updateLots(self, sym, lots):
        if lots:
            self.lots[sym] = lots
        else:
            try:
                del self.lots[sym]
            except KeyError:
                pass

    # def adjustWashSaleLot(self, lt, clt, days):
    #     # print('adjustWashSaleLot', str(clt), days)
    #     ns = min(clt.nshares - clt.wash_shares, lt.nshares)
    #     if ns <= 0:
    #         return None
    #     gain = clt.getGain()
    #     ws = math.ceil(100 * ns * (-gain - clt.wash_sale) /
    #                    (clt.nshares - clt.wash_shares)) * 0.01
    #     lt2 = None
    #     if ns < lt.nshares:
    #         lt2 = copy.deepcopy(lt)
    #         lt2.nshares -= ns
    #         factor = ns / lt.nshares
    #         adjustDividends(lt2.dividends, 1 - factor)
    #         adjustDividends(lt2.return_of_capital, 1 - factor)
    #         adjustDividends(lt.dividends, factor)
    #         adjustDividends(lt.return_of_capital, factor)
    #         lt.nshares = ns
    #     lt.dividends += [Dividend(d.date, d.amount * ns / clt.nshares)
    #                     for d in clt.dividends]
    #     lt.purchase_date -= clt.end_date - clt.start_date
    #     lt.share_adj += ws / ns
    #     clt.wash_sale += ws
    #     clt.wash_shares += ns
    #     clt.wash_days.append(days)
    #     # print(clt.wash_days)
    #     return lt2

    # def adjustWashSaleAfter(self, lots, completed):
    #     # print('adjustWashSaleAfter', [str(cl) for cl in completed])
    #     used_lots = []
    #     for cl in completed:
    #         if cl.getGain() < 0:
    #             remaining_lots = []
    #             for lt in lots:
    #                 if cl.end_date - lt.purchase_date <= 30:
    #                     lt2 = self.adjustWashSaleLot(lt, cl, cl.end_date - lt.purchase_date)
    #                     if lt2:
    #                         remaining_lots.append(lt2)
    #                     used_lots.append(lt)
    #                 else:
    #                     remaining_lots.append(lt)
    #             lots = remaining_lots
    #     lots += used_lots
    #     lots.sort(key=lambda lt: lt.purchase_date)
    #     return lots

    # def adjustWashSaleBefore(self, lots, completed, date):
    #     # print('adjustWashSaleBefore', [str(cl) for cl in completed])
    #     lt = lots.pop()
    #     for cl in completed:
    #         lt2 = self.adjustWashSaleLot(lt, cl, Transaction.toDate(date))
    #         lots.append(lt)
    #         if lt2:
    #             lt = lt2
    #         else:
    #             break
    #     lots.sort(key=lambda lt: lt.purchase_date)
    #     # print([(str(lt), Transaction.toDate(lt.purchase_date)) for lt in lots])
    #     return lots

    def checkWashSell(self, completed):
        completed = [clt for clt in completed if clt.getGain() < 0]
        if not completed:
            return
        sym = completed[0].symbol
        # if sym == 'AAPL120317C00540000':
        #     print('checkWashSell', [str(clt) for clt in completed])
        found = False
        for clt in completed:
            matches = [lt for lt in self.recent_buys if lt.symbol == sym]
            if not matches:
                break
            found = True
            # print('match3', [(str(clt), clt.getGain()) for clt in completed], [str(lt) for lt in matches])
            share_gain = clt.getGain() / clt.nshares
            remaining = clt.nshares
            for lt in matches:
                if lt.nshares <= clt.nshares:
                    self.recent_buys.remove(lt)
                    if lt.nshares < clt.nshares:
                        clt = self.splitCompletedLot(
                            clt, clt.nshares - lt.nshares)
                    else:
                        self.recent_sells.remove(clt)
                    remaining -= lt.nshares
                else:
                    self.recent_sells.remove(clt)
                    lt, _ = self.splitLot(lt, lt.nshares - clt.nshares)
                    remaining = 0
                lt.share_adj -= share_gain
                lt.wash_days = clt.end_date - clt.start_date
                clt.end_share_adj += share_gain
                clt.wash_sale = -share_gain
                if remaining == 0:
                    break
        # if found:
        #     matches = [lt for lt in self.recent_buys if lt.symbol == sym]
        #     print('match4', [(str(clt), clt.getGain()) for clt in completed], [str(lt) for lt in matches], [str(clt) for clt in self.recent_sells if clt.symbol == sym])

    def checkWashBuy(self, lt):
        matches = [clt for clt in self.recent_sells
                   if clt.symbol == lt.symbol and clt.getGain() < 0]
        if not matches:
            return
        # if lt.symbol == 'AAPL120317C00540000':
        #     print('checkWashBuy', [str(clt) for clt in matches],
        #           [str(lt) for lt in self.lots[lt.symbol]])
        # print('match1', str(lt), [str(clt) for clt in matches])
        remove = []
        remaining = lt.nshares
        completed = []
        lt2 = lt
        for clt in matches:
            lt = lt2
            # if lt.symbol == 'AAPL120317C00540000':
            #     print('match', lt.nshares, str(clt), [str(x) for x in self.recent_buys])
            share_gain = clt.getGain() / clt.nshares
            completed.append(clt)
            if clt.nshares <= lt.nshares:
                self.recent_sells.remove(clt)
                if clt.nshares < lt.nshares:
                    # The remaining shares stay in recent_buys
                    lt, lt2 = self.splitLot(lt, lt.nshares - clt.nshares)
                else:
                    self.recent_buys.remove(lt)
                remaining -= clt.nshares
            else:
                self.recent_buys.remove(lt)
                # The remaining completed shares stay in recent_sells
                clt = self.splitCompletedLot(clt, clt.nshares - lt.nshares)
                remaining = 0
            lt.share_adj -= share_gain
            lt.wash_days = clt.end_date - clt.start_date
            clt.end_share_adj += share_gain
            clt.wash_sale = -share_gain
            if remaining == 0:
                break
        matches = [clt for clt in self.recent_sells
                   if clt.symbol == lt.symbol and clt.getGain() < 0]
        # print('match2', str(lt), [str(x) for x in self.recent_buys if x.symbol == lt.symbol],
        #       [str(clt) for clt in matches], [str(clt) for clt in completed])

    def sellShares(self, sym, count, share_price, share_expense, share_adj,
                   share_proceeds, date):
        lots = self.lots[sym]
        # if sym == 'AAPL120317C00540000':
        #     print('sellShares', sym, count, [str(lt) for lt in lots])
        ncompleted = 0
        for lt in lots:
            amount, count = self.sellLot(lt, count, share_price,
                                         share_expense, share_adj,
                                         share_proceeds, date)
            if amount != 0:
                if lt.nshares == 0:
                    try:
                        self.recent_buys.remove(lt)
                    except ValueError:
                        pass
                ncompleted += 1
            if count <= 0:
                break
        lots = [lt for lt in lots if lt.nshares != 0]
        self.updateLots(sym, lots)
        if ncompleted:
            self.checkWashSell(self.completed_lots[-ncompleted:])
        #     matches = [lt for lt in self.recent_buys if lt.symbol == sym]
        #     if matches:
        #         print('match3',
        #               [str(clt) for clt in self.completed_lots[-ncompleted:]],
        #               [str(lt) for lt in matches])
        #     lots = self.adjustWashSaleAfter(
        #         lots, self.completed_lots[-ncompleted:])
        # if sym == 'AAPL120317C00540000':
        #     print('sellShares2', sym, count, ncompleted, [str(lt) for lt in lots])
        if count > 0.001:
            lots.append(self.createLot(sym, -count, share_price,
                                       share_expense, share_adj, date))
        self.updateLots(sym, lots)

    def buyShares(self, sym, count, share_price, share_expense, share_adj,
                  date):
        lots = self.lots[sym]
        # if sym == 'AAPL120317C00540000':
        #     print('buyShares', sym, count, [str(lt) for lt in lots])
        for lt in lots:
            amount, count = self.buyLot(lt, count, share_price,
                                        share_expense, share_adj, date)
            if count <= 0:
                break
        lots = [lt for lt in lots if lt.nshares != 0]
        self.updateLots(sym, lots)
        # if sym == 'AAPL120317C00540000':
        #     print('buyShares2', sym, count, [str(lt) for lt in lots])
        if count > 0.001:
            lt = self.createLot(sym, count, share_price,
                                share_expense, share_adj, date)
            lots.append(lt)
            # Need the update here because the previous update didn't do
            # anything if there were no lots.
            self.updateLots(sym, lots)
            # if sym == 'AAPL120317C00540000':
            #     print('buyShares2a', sym, lots, self.lots[sym])
            self.recent_buys.append(lt)
            self.checkWashBuy(lt)
            # completed = [cl for cl in self.completed_lots
            #              if cl.symbol == sym and cl.end_date >= date - 30 and
            #              cl.nshares - cl.wash_shares > 0 and cl.getGain() < 0]
            # if completed:
            #     lots = self.adjustWashSaleBefore(lots, completed, date)
        # if sym == 'AAPL120317C00540000':
        #     print('buyShares3', sym, count, [str(lt) for lt in lots])
        self.updateLots(sym, lots)

    def assignOption(self, option):
        if option.type == 'b':
            self.handleBuy(option)
            remaining = option.count
        else:
            self.handleSell(option)
            remaining = -option.count
        # for i in range(-3, 0):
        #     print(i, str(self.completed_lots[i]))
        assigned = []
        while remaining != 0:
            cl = self.completed_lots.pop()
            remaining += cl.nshares
            assigned.append(cl)
        assigned.reverse()
        self.assigned_lots += assigned
        return assigned

    def handleBuy(self, t, option=None):
        # https://www.marketwatch.com/story/how-stock-options-are-taxed-2015-03-18
        # If you exercise a put option by selling stock to the writer at the
        # designated price, deduct the option cost (the premium plus any
        # transaction costs) from the proceeds of your sale. Your capital
        # gain or loss is long term or short term depending on how long you
        # owned the underlying stock.
        #
        # If you exercise a call option by buying stock from the writer at
        # the designated price, add the option cost to the price paid for the
        # shares. This becomes your tax basis.
        #
        # If you write a put option that gets exercised (meaning you have to
        # buy the stock), reduce the tax basis of the shares you acquire by
        # the premium you received.
        #
        # If you write a call option that gets exercised (meaning you sell
        # the stock), add the premium to the sales proceeds.
        share_expense = t.amount2 / t.count if t.count > 0 else 0
        # if t.name == 'AAPL120317C00540000':
        #     print('handleBuy', str(t))
        amount = t.count * t.amount1 + t.amount2
        if t.is_cash_like():
            self.cash_like += amount
            if t.date == self.portfolio_date:
                self.cash_like_diff += amount
        elif option:
            # print('buy:', str(t), str(option))
            assigned = self.assignOption(option)
            for cl in assigned:
                sgn = math.copysign(1, cl.nshares)
                # end_share_price and end_share_expense are 0 for
                # assigned options
                share_adj = cl.start_share_price * sgn + cl.start_share_expense
                self.buyShares(t.name, cl.nshares * sgn, t.amount1,
                               share_expense, share_adj, t.date)
            # print('buy:', str(t), str(option))
            # for k, lots in self.lots.items():
            #     for lt in lots:
            #         print(str(lt))
        elif t.count > 0:
            self.buyShares(t.name, t.count, t.amount1, share_expense,
                           0, t.date)
        self.cash -= amount
        if t.date == self.portfolio_date:
            self.cash_diff -= amount
        # if t.name == 'AAPL120317C00540000':
        #     for lt in self.lots[t.name]:
        #         print(str(lt))

    def handleSell(self, t, option=None):
        # if t.name == 'AAPL120317C00540000':
        #     print('handleSell', str(t))
        amount = t.count * t.amount1 - t.amount2
        share_expense = t.amount2 / t.count if t.count > 0 else 0
        if t.is_cash_like():
            self.cash_like -= amount
            if t.date == self.portfolio_date:
                self.cash_like_diff -= amount
        elif option:
            # print('sell:', str(t), str(option))
            assigned = self.assignOption(option)
            for a in assigned:
                sgn = math.copysign(1, a.nshares)
                share_adj = a.start_share_price * sgn + a.start_share_expense
                self.sellShares(t.name, a.nshares * sgn, t.amount1,
                                share_expense, share_adj,
                                amount / (a.nshares * sgn), t.date)
                # print(share_adj, str(a))
        elif t.count > 0:
            self.sellShares(t.name, t.count, t.amount1, share_expense,
                            0, amount / t.count, t.date)
            # self.matchOption(t, future, basis)
        self.cash += amount
        if t.date == self.portfolio_date:
            self.cash_diff += amount
        # if t.name == 'AAPL120317C00540000':
        #     for lt in self.lots[t.name]:
        #         print(str(lt))

    def handleInterest(self, t, year):
        amount = t.amount1
        date = t.date
        self.cash += amount
        if date == self.portfolio_date:
            self.cash_diff += amount
        self.interest_total += amount
        self.year_dividend[year][t.name] += amount
        lots = self.lots[t.name]
        total_shares = sum(lt.nshares for lt in lots if lt.purchase_date < date)
        for lt in lots:
            if lt.purchase_date < date:
                dividend = Dividend(date, amount * lt.nshares / total_shares)
                if t.type == 'i':
                    lt.dividends.append(dividend)
                else:
                    lt.return_of_capital.append(dividend)
        if date >= self.bg_year:
            it = next((it for it in self.interest if it.name == t.name), None)
            if it is None:
                self.interest.append(Interest(t.name, amount))
            else:
                it.amount += amount

    def handleCashConsideration(self, t):
        # In some mergers, part of the consideration is provided in the form of cash. For
        # example, in a 1999 merger, shareholders of AirTouch received .5 shares of new
        # Vodaphone AirTouch ADS plus $9.00 in cash for each common share they
        # owned. Here's how you figure your gain:
        #
        # Step 1: Determine the overall gain you have on the exchange. To do this, you
        # need to know the value of the merger consideration, including both shares and
        # stock. Generally the company gives you this information at the time of the
        # merger. If you can't find this information, it's likely to be on the company's
        # web site. Multiply that figure times the number of shares you held to determine
        # the total consideration you received. Then subtract your total basis in the
        # shares you held to get the overall gain.
        #
        # Step 2: The amount of gain you report is the lesser of the amount of gain from
        # step 1 or the amount of cash you received.
        #
        # Step 3: Your basis in the shares you received is equal to your basis in the old
        # shares, increased by the amount of gain you reported and decreased by the amount
        # of cash you received.
        #
        # Example: Suppose you held 100 shares of AirTouch common before the merger. The
        # merger consideration was $107.50 per share, so your total consideration was
        # $10,750, of which you received $900 in cash.
        #
        # If the total basis in your AirTouch shares before the merger was $8,000, your
        # gain was $2,750. That's more than the amount of cash you received, so you report
        # gain of $900, and your basis in the new shares is $8,000.
        #
        # If the total basis in your AirTouch shares before the merger was $10,000, your
        # gain was $750. You report only $750 of gain, even though you received $900 in
        # cash. The other $150 reduces your basis in the new shares to $9,850.
        #
        # Finally, if the total basis in your AirTouch shares before the merger was
        # $12,000, you have a loss on the merger transaction. You can't report this loss
        # on your return, but you get to receive the $900 without reporting any gain at
        # all. This reduces your basis in the new shares to $11,100.
        total_shares = 0
        total_cost = 0
        for lt in self.lots[t.name]:
            total_shares += lt.nshares
            total_cost += lt.nshares * lt.share_price + abs(lt.nshares) * lt.share_expense
            adjustDividends(lt.dividends, (1 - t.amount2))
            adjustDividends(lt.return_of_capital, (1 - t.amount2))
        proceeds = total_shares * t.amount1
        # amount2: fraction of transaction paid in cash
        total_value = total_shares * t.amount1 / t.amount2
        gain = total_value - total_cost
        if gain > proceeds:
          gain = proceeds
        elif gain < 0:
          gain = 0
        if t.date == self.portfolio_date and not t.is_cash_like():
            self.equity_diff -= proceeds
        if gain > 0 and t.date >= self.bg_year:
            for lt in self.lots[t.name]:
              if t.date - lt.purchase_date >= LONG_DAYS:
                  self.realized_long += gain * lt.nshares / total_shares
              else:
                  self.realized_short += gain * lt.nshares / total_shares
        if gain != proceeds:
            for lt in self.lots[t.name]:
                lt.share_price += (gain - proceeds) / total_shares
        self.cash += proceeds
        if t.date == self.portfolio_date:
          self.cash_diff += proceeds

    def mergeLots(self, symbol, lots):
        lots2 = self.lots[symbol]
        if lots2:
            lots2 += lots
            lots2.sort(key=lambda lt: lt.purchase_date)
        else:
            self.lots[symbol] = lots

    def handleChange(self, t):
        if t.amount1 > 0:
            self.handleCashConsideration(t)
        lots = self.lots[t.name]
        for lt in lots:
            lt.symbol = t.name2
            lt.nshares *= t.count
            lt.share_price /= t.count
            lt.share_expense /= t.count
            lt.share_adj /= t.count
        if t.name2 != t.name:
            # Same names should really be handled by 'x'.
            self.mergeLots(t.name2, lots)
            del self.lots[t.name]
        for it in self.interest:
            if it.name == t.name:
                it.name = t.name2

    def handleSpinoff(self, t):
        # spin-off
        # amount1: number of shares for each share of original stock
        # amount2: share_price(new stock) / share_price(original stock) at spin-off date
        # Schwab recommends using the opening price.
        value_fraction = t.amount1 * t.amount2
        value_fraction /= 1 + value_fraction
        count = 0
        new_lots = []
        lots = self.lots[t.name]
        for lt in lots:
            expense1 = lt.nshares * lt.share_expense
            expense2 = value_fraction * expense1
            expense1 -= expense2
            adj1 = lt.nshares * lt.share_adj
            adj2 = value_fraction * adj1
            adj1 -= adj2
            nshares = lt.nshares * t.amount1
            lt.share_expense = expense1 / lt.nshares
            lt.share_adj = adj1 / lt.nshares
            lt.share_price *= 1 - value_fraction
            new_lots.append(self.createLot(
                t.name2, nshares, lt.share_price * t.amount2,
                expense2 / nshares, adj2 / nshares, lt.purchase_date))
        self.mergeLots(t.name2, new_lots)

    def handleSplit(self, t):
        if t.name2 and t.name2 != t.name:
            self.handleSpinoff(t)
        else:
            # regular stock split
            fraction = 1 + t.amount1
            for lt in self.lots[t.name]:
                lt.nshares *= fraction
                lt.share_price /= fraction
                lt.share_expense /= fraction
                lt.share_adj /= fraction

    def handleDeposit(self, t):
        amount = t.amount1
        self.deposits.append((t.date, t.amount1))
        if t.date != self.portfolio_date:
            self.cash += amount
        else:
            self.new_deposits += amount
        # Deposits of the current day didn't use to be included in
        # total_deposits but this is more useful for the account chart.
        self.total_deposits += amount
        if t.date >= self.bg_year:
            if t.date < self.first_deposit:
                self.first_deposit = t.date

    @staticmethod
    def matchOptions(group):
        stocks = [idx for idx, t in enumerate(group)
                  if (t.type == 'b' or t.type == 's') and
                  not isOptionSymbol(t.name)]
        while stocks:
            idx1 = stocks.pop(0)
            t = group[idx1]
            idx2 = -1
            for i in range(len(group)):
                if i == idx1:
                    continue
                t2 = group[i]
                if (isinstance(t2, tuple) or
                    (t2.type != 'b' and t2.type != 's') or t2.amount1 != 0):
                    continue
                opt = getOptionParameters(t2.name)
                if (opt[0] == t.name and opt[3] == t.amount1 and
                    (t2.type == t.type) == (opt[2] == 'P')):
                    idx2 = i
                    break
            if idx2 >= 0:
                group[idx1] = (t, group[idx2])
                group.pop(idx2)
                for i in range(len(stocks)):
                    if stocks[i] > idx2:
                        stocks[i] -= 1
        return group

    def fillLots(self, transactions):
        # This is the main method for adding transactions to the portfolio.
        self.transactions = transactions
        year = 0
        year_end = 0
        for k, g in groupby(transactions, lambda t: t.date):
            idx = next((i for i, lt in enumerate(self.recent_buys)
                        if lt.purchase_date > k - 31),
                       len(self.recent_buys))
            del self.recent_buys[:idx]
            idx = next((i for i, lt in enumerate(self.recent_sells)
                        if lt.end_date > k - 31),
                       len(self.recent_sells))
            del self.recent_sells[:idx]
            # The transactions have to be kept in order other than matching
            # stocks with options.
            group = Portfolio.matchOptions(list(g))
            # if k == 18361:
            #     print('group', Transaction.toDate(k).isoformat(),
            #           [(str(x[0]), str(x[1]))
            #            if isinstance(x, tuple) else str(x)
            #            for x in group])
            for t in group:
                if isinstance(t, tuple):
                    if t[0].type == 'b':
                        self.handleBuy(t[0], t[1])
                    else:
                        self.handleSell(t[0], t[1])
                elif t.type == 'b':
                    self.handleBuy(t)
                elif t.type == 's':
                    self.handleSell(t)
                elif t.type == 'i' or t.type == 'r':
                    if t.date >= year_end:
                        year = Transaction.toYear(t.date)
                        year_end = Transaction.fromYear(year + 1)
                    self.handleInterest(t, year)
                elif t.type == 'c':
                    self.handleChange(t)
                elif t.type == 'x':
                    self.handleSplit(t)
                elif t.type == 'd':
                    self.handleDeposit(t)

    def getCurrentSymbols(self):
        symbols = set(s for k, v in self.lots.items()
                      if v for s in getOptionPair(k))
        if self.cash_like:
            # for report.cgi
            symbols |= cash_like
        return sorted(symbols)

    def toDict(self, year=None, all=False):
        data = makeDict(self, ['cash', 'cash_diff', 'cash_like',
                               'cash_like_diff', 'equity_diff',
                               'new_deposits'])
        keys = sorted(self.lots)
        data['lots'] = [lt.toDict() for k in keys for lt in self.lots[k]]
        data['deposits'] = self.deposits
        if all:
            cl = [lt.toDict() for lt in self.completed_lots]
            data['completed_lots'] = cl
            assigned = [lt.toDict() for lt in self.assigned_lots]
            data['assigned_lots'] = assigned
        elif year:
            year = int(year)
            start = Transaction.fromYear(year)
            end = Transaction.fromYear(year + 1)
            cl = [lt.toDict() for lt in self.completed_lots
                  if lt.end_date >= start and lt.end_date < end]
            data['completed_lots'] = cl
            data['dividend'] = self.year_dividend[year]
        return data

    @staticmethod
    def combine(portfolios):
        if len(portfolios) == 0:
            return None
        elif len(portfolios) == 1:
            return portfolios[0]
        portfolio = Portfolio(portfolios[0].portfolio_date)
        keys = sorted(set([k for p in portfolios for k in p.lots]))
        portfolio.lots = defaultdict(list,
                                     {k: [lt for p in portfolios
                                          for lt in p.lots.get(k, [])]
                                      for k in keys})
        portfolio.completed_lots = [lt for p in portfolios
                                    for lt in p.completed_lots]
        portfolio.assigned_lots = [lt for p in portfolios
                                   for lt in p.assigned_lots]
        portfolio.sortLots()
        portfolio.interest = [i for p in portfolios for i in p.interest]
        portfolio.deposits = [d for p in portfolios for d in p.deposits]
        portfolio.sortDeposits()
        portfolio.first_deposit = min(p.first_deposit for p in portfolios)
        portfolio.realized_long = sum(p.realized_long for p in portfolios)
        portfolio.realized_short = sum(p.realized_short for p in portfolios)
        portfolio.purchase_total = sum(p.purchase_total for p in portfolios)
        portfolio.interest_total = sum(p.interest_total for p in portfolios)
        portfolio.cash = sum(p.cash for p in portfolios)
        portfolio.cash_diff = sum(p.cash_diff for p in portfolios)
        portfolio.cash_like = sum(p.cash_like for p in portfolios)
        portfolio.cash_like_diff = sum(p.cash_like_diff for p in portfolios)
        portfolio.equity_diff = sum(p.equity_diff for p in portfolios)
        portfolio.new_deposits = sum(p.new_deposits for p in portfolios)
        portfolio.total_deposits = sum(p.total_deposits for p in portfolios)
        years = set(y for p in portfolios for y in p.year_dividend)
        for y in years:
            keys = set([k for p in portfolios for k in p.year_dividend[y]])
            # No need to use "get" because p.year_dividend has nested
            # defaultdicts
            d = defaultdict(float,
                            {k: sum(p.year_dividend[y][k] for p in portfolios)
                             for k in keys})
            portfolio.year_dividend[y] = d
        return portfolio

    @staticmethod
    def get_files(data_dir, account, date=None):
        Portfolio.get_transfers(data_dir)
        if not account:
            files = Transaction.getAccounts(data_dir)[:1]
        elif account == 'combined' or account == 'all':
            files = Transaction.getAccounts(data_dir)
        elif account == 'taxable':
            files = ['ag-broker', 'al-broker', 'ameritrade', 'microsoft']
        else:
            files = [account]
        if date:
            drop = set([a[1] for a in Portfolio.account_transfers
                        if Transaction.parseDate(a[0]) <= date])
            files = [f for f in files if f not in drop]
        return files

    @staticmethod
    def get_transfers(data_dir):
        Portfolio.account_transfers = []
        try:
            with open(os.path.join(data_dir, 'transfers'),
                      encoding='utf-8') as f:
                for x in f:
                    val = x.split('#', 1)[0].rstrip().split('|')
                    if len(val) >= 3:
                        Portfolio.account_transfers.append(val)
        except FileNotFoundError:
            pass

    @staticmethod
    def readTransfers(date, account, skip=None):
        accounts = [(Transaction.parseDate(a[0]), a[1])
                    for a in Portfolio.account_transfers
                    if a[2] == account and Transaction.parseDate(a[0]) <= date]
        accounts.sort()
        accounts = [(a[0], a[1],
                     Transaction.readTransactions(os.path.join(data_dir, a[1]),
                                                  a[0], skip=skip))
                    for a in accounts]
        return [a for a in accounts if a[2]]

    @staticmethod
    def getHistory(account, start=0, end=None, include_positions=False):
        end = end or Transaction.today()
        accounts = [(Transaction.parseDate(a[0]), a[1])
                    for a in Portfolio.account_transfers
                    if a[2] == account and Transaction.parseDate(a[0]) <= end]
        accounts.sort()
        for a in accounts:
            updateHistory(a[1], date=a[0])
        updateHistory(account, date=end, accounts=accounts)
        # Don't include the merge day because it's already in the merged
        # account.
        accounts = [(end, account)] + [(a[0] - 1, a[1]) for a in accounts]
        columns = ['date', 'equity', 'cash', 'deposits']
        if include_positions:
            columns.append('positions')
        account_rows = []
        for a in accounts:
            cursor = getCursor(os.path.join(cache_dir, '{0}.db'.format(a[1])))
            try:
                cursor.execute('SELECT {0} FROM positions WHERE date>=? AND date<=?'
                               .format(','.join(columns)),
                               [start, a[0]])
                rows = cursor.fetchall()
                if include_positions:
                    rows = [r[:4] + (json.loads(r[4]),) for r in rows]
                account_rows.append(rows)
            finally:
                cursor.connection.close()
        n = len(account_rows)
        if n == 1:
            rows = account_rows[0]
        else:
            dates = sorted(reduce(lambda x, y: x | set(z[0] for z in y),
                                  account_rows, set()))
            rows = []
            indices = [0] * n
            for d in dates:
                entries = []
                for i in range(n):
                    if (indices[i] < len(account_rows[i]) and
                        account_rows[i][indices[i]][0] == d):
                        entries.append(account_rows[i][indices[i]])
                        indices[i] += 1
                rows.append(mergeHistoryEntries(entries))
        return [{c: (Transaction.toDate(r[i]).isoformat() if i == 0 else r[i])
                 for i, c in enumerate(columns)}
                for r in rows]


def mergeHistoryEntries(entries):
    # date, equity, cash, deposits, positions
    if len(entries) == 1:
        return entries[0]
    merged = [entries[0][0]] + [sum(e[i] for e in entries) for i in range(1, 4)]
    if len(entries[0]) > 4:
        quotes = {}
        positions = defaultdict(float)
        for e in entries:
            data = e[4]
            for p in data:
                quotes[p[0]] = p[2]
                positions[p[0]] += p[1]
        symbols = sorted(positions.keys())
        merged.append([[s, positions[s], quotes[s]] for s in symbols])
    return merged


def updateHistory(account, date=None, accounts=[]):
    date = date or Transaction.today()
    accounts = [(a[0], a[1],
                 Transaction.readTransactions(os.path.join(data_dir, a[1]), a[0]))
                for a in accounts]
    accounts = [a for a in accounts if a[2]]
    # Process merged portfolios until merge dates
    portfolios = [Portfolio(a[0]) for a in accounts]
    for i, a in enumerate(accounts):
        portfolios[i].fillLots(a[2])
    c = getCursor(os.path.join(cache_dir, '{0}.db'.format(account)))
    try:
        portfolio = Portfolio(date)
        portfolio.account = account
        createPositionsTable(c)
        trans = Transaction.readTransactions(os.path.join(data_dir, account), date)
        start = trans[0].date
        if accounts:
            start = min(start, min(a[2][0].date for a in accounts))
        # "start" is before the range
        start -= 1
        c.execute('SELECT MAX(date) FROM positions')
        row = c.fetchone()
        if row[0]:
            start = max(start, row[0])
        quote_dates = getQuoteDates(Transaction.toDate(start + 1),
                                    Transaction.toDate(date))
        # Always fill the lots from the beginning.
        start = 0
        quotes = {}
        for d in quote_dates:
            end = Transaction.fromDate(d)
            portfolio.fillLots([t for t in trans
                                if t.date > start and t.date <= end])
            for i, a in enumerate(accounts):
                if a[0] > start and a[0] <= end:
                    portfolio = Portfolio.combine([portfolio,
                                                   portfolios[i]])
            positions = [(k, n) for k, n
                         in ((k, sum(lt.nshares for lt in v))
                             for k, v in portfolio.lots.items())
                         if n]
            positions.sort()
            # Use quotes from previous days if current quotes are missing
            quotes.update(getQuotes(d, [p[0] for p in positions] if positions else {}))
            positions = [(p[0], p[1], quotes.get(p[0], 0)) for p in positions]
            equity = round(sum(p[1] * p[2] for p in positions), 2)
            cash = round(portfolio.cash + portfolio.cash_like, 2)
            deposits = round(portfolio.total_deposits, 2)
            c.execute('INSERT INTO positions '
                      '(date,equity,cash,deposits,positions) '
                      'VALUES(?,?,?,?,?)',
                      (end, equity, cash, deposits,
                       json.dumps(positions, separators=(',',':'))))
            # print(d, data)
            start = end
        c.connection.commit()
    finally:
        c.connection.close()


def getCursor(name):
    conn = sqlite3.connect(name)
    return conn.cursor()


def createPositionsTable(cursor):
    cursor.execute('CREATE TABLE IF NOT EXISTS positions '
                   '(date INTEGER PRIMARY KEY, equity REAL, cash REAL, '
                   'deposits REAL, positions TEXT)')


def setDataPaths(data_path, cache_path):
    global data_dir, cache_dir
    data_dir = data_path
    cache_dir = cache_path


def main2(argv):
    date = Transaction.parseDate(argv[2]) if len(argv) > 2 else Transaction.today()
    skip = None
    # skip = 'options'
    files = Portfolio.get_files(data_dir, argv[1], date)
    portfolios = []
    for f in files:
        trans = Transaction.readTransactions(os.path.join(data_dir, f), date, skip=skip)
        # print(trans[-1])
        # print([str(t) for t in trans[-4:]])
        append = bool(trans)
        accounts = [(Transaction.parseDate(a[0]), a[1])
                    for a in Portfolio.account_transfers
                    if a[2] == f and Transaction.parseDate(a[0]) <= date]
        accounts.sort()
        portfolio = Portfolio(date)
        portfolio.account = f
        start = 0
        for a in accounts:
            end = a[0]
            portfolio.fillLots([t for t in trans
                                if t.date > start and t.date <= end])
            start = end
            trans2 = Transaction.readTransactions(os.path.join(data_dir, a[1]), a[0], skip=skip)
            if trans2:
                append = True
                p = Portfolio(a[0])
                p.account = f
                p.fillLots(trans2)
                portfolio = Portfolio.combine([portfolio, p])
                portfolio.account = f
        portfolio.fillLots([t for t in trans if t.date > start])
        if append:
            portfolios.append(portfolio)
            # print(f)
            # for k, lots in portfolio.lots.items():
            #     for lt in lots:
            #         print(str(lt), getattr(lt, 'account', None))
    portfolio = Portfolio.combine(portfolios)
    print(portfolio.cash + portfolio.cash_like)
    # print(portfolio.getCurrentSymbols())
    # for k, lots in portfolio.lots.items():
    #     for lt in lots:
    #         print(str(lt), getattr(lt, 'account', None))
    # print(portfolio.year_dividend)


def main(argv):
    start = argv[2] if len(argv) > 2 else '2020-03-30'
    end = argv[3] if len(argv) > 3 else '2020-04-30'
    history = Portfolio.getHistory(argv[1],
                                   start=Transaction.parseDate(start),
                                   end=Transaction.parseDate(end),
                                   include_positions=True)
    if history:
        print('last history', history[-1])
    # print(Portfolio.getHistory('ameritrade',
    #                            start=Transaction.fromDate(datetime.date(2020, 1, 1)),
    #                            include_positions=True)[0])
    # print(Portfolio.getHistory('ag-broker',
    #                            start=Transaction.fromDate(datetime.date(2020, 1, 1)),
    #                            end=Transaction.fromDate(datetime.date(2020, 1, 1)),
    #                            include_positions=True)[0])


if __name__ == '__main__':
    main2(sys.argv)
