#!/usr/bin/python3

from collections import defaultdict
import copy
import datetime
from itertools import groupby
import math
import os
import re
import sys


EPOCH = datetime.date(1970, 1, 1)
LONG_DAYS = 365

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


class Bucket:
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
        self.dividends = []
        self.return_of_capital = []

    def __str__(self):
        return ('%s|%.3f|%.2f|%.5f|%d|%.5f' %
                (self.symbol, self.nshares, self.share_price,
                 self.share_expense, self.purchase_date, self.share_adj))

    def toDict(self):
        data = makeDict(self, ['symbol', 'nshares', 'share_price',
                               'share_expense', 'share_adj', 'account'])
        for k in ['dividends', 'return_of_capital']:
            v = getattr(self, k)
            if v:
                data[k] = [x.toDict() for x in v]
        data['purchase_date'] = Transaction.toDate(self.purchase_date).isoformat()
        return data


class CompletedBucket:
    def __init__(self, bucket, end_date, nshares, end_share_price,
                 end_share_expense, end_share_adj):
        self.symbol = bucket.symbol
        self.start_date = bucket.purchase_date
        self.end_date = end_date
        self.nshares = nshares
        self.start_share_price = bucket.share_price
        self.end_share_price = end_share_price
        self.start_share_expense = bucket.share_expense
        self.end_share_expense = end_share_expense
        self.start_share_adj = bucket.share_adj
        self.end_share_adj = end_share_adj
        self.wash_sale = 0
        self.wash_shares = 0
        # Always copy the dividends because they will be adjusted to 0 after
        # the transaction.
        self.dividends = [Dividend(d.date,
                                   d.amount * nshares / bucket.nshares)
                          for d in bucket.dividends]
        account = getattr(bucket, 'account', None)
        if account is not None:
            self.account = account

    def __str__(self):
        return ('%s|%.3f|%.2f|%.2f|%.5f|%.5f|%.5f|%.5f|%d|%d' %
                (self.symbol, self.nshares, self.start_share_price,
                 self.end_share_price, self.start_share_expense,
                 self.end_share_expense, self.start_share_adj,
                 self.end_share_adj, self.start_date, self.end_date))

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
                   'start_share_adj', 'end_share_adj', 'wash_sale', 'account'])
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
        for f in os.listdir(path):
            if not f.startswith('.') and not f.endswith('~'):
                files.append(f)
        files.sort()
        return files

    @staticmethod
    def readTransactions(filename, date=None):
        if date is None:
            date = Transaction.today()
        transactions = []
        with open(filename, encoding='utf-8') as f:
            for x in f:
                t = Transaction.parse(x)
                if t is None:
                    continue
                if t.date > date:
                    break
                transactions.append(t)
        # transactions.sort(key=lambda t: t.date)
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
            if (t.type == 's' or t.type == 'b') and not isOptionSymbol(t.name):
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
                        print(Transaction.toDate(t.date).isoformat(), str(t), ' ', str(t2))


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
    def __init__(self, date, account=None):
        self.portfolio_date = date
        self.account = account
        self.bg_year = Transaction.yearBegin(date)
        self.first_deposit = self.bg_year + 366
        self.buckets = defaultdict(list)
        self.completed_buckets = []
        self.assigned_buckets = []
        self.interest = []
        self.realized_long = 0
        self.realized_short = 0
        self.purchase_total = 0
        self.unrealized_total = 0
        self.sales_total = 0
        self.interest_total = 0
        self.cash = 0
        self.cash_diff = 0
        self.equity_diff = 0
        self.new_deposits = 0
        self.total_deposits = 0
        self.year_yield = 0
        self.year_dividend = defaultdict(lambda: defaultdict(float))

    def emptyBuckets(self):
        self.buckets = defaultdict(list)

    def combineBuckets(self, all_buckets):
        keys = sorted(set([k for ab in all_buckets for k in ab]))
        self.buckets = {k: [b for ab in all_buckets for b in ab.get(k, [])]
                        for k in keys}

    def createBucket(self, symbol, nshares, share_price, share_expense,
                     share_adj, purchase_date):
        b = Bucket(symbol, nshares, share_price, share_expense, share_adj,
                   purchase_date)
        if self.account is not None:
            b.account = self.account
        return b

    def sellBucket(self, b, sold_shares, share_price, share_expense, share_adj,
                   share_proceeds, date):
        current_shares = sold_shares
        if b.nshares <= 0:
            return (0, sold_shares)
        if current_shares > b.nshares:
            current_shares = b.nshares
        sold_shares -= current_shares
        factor = (b.nshares - current_shares) / b.nshares
        amount = current_shares * (b.share_price + b.share_expense)
        cb = CompletedBucket(b, date, current_shares, share_price,
                             share_expense, share_adj)
        self.completed_buckets.append(cb)
        b.nshares -= current_shares
        if b.nshares < 0.0001:
            b.nshares = 0
        adjustDividends(b.dividends, factor)
        adjustDividends(b.return_of_capital, factor)
        self.purchase_total += amount
        if date >= self.bg_year:
            if date - b.purchase_date >= LONG_DAYS:
                self.realized_long += (share_proceeds * current_shares -
                                       amount)
            else:
                self.realized_short += (share_proceeds * current_shares -
                                        amount)
        return (amount, sold_shares)

    def buyBucket(self, b, bought_shares, share_price, share_expense,
                  share_adj, date):
        current_shares = bought_shares
        if b.nshares >= 0:
            return (0, bought_shares)
        if current_shares > -b.nshares:
            current_shares = -b.nshares
        bought_shares -= current_shares
        amount = current_shares * (b.share_price + b.share_expense)
        cb = CompletedBucket(b, date, -current_shares, share_price,
                             share_expense, share_adj)
        self.completed_buckets.append(cb)
        b.nshares += current_shares
        if b.nshares > -0.0001:
            b.nshares = 0
        return (amount, bought_shares)

    def updateBuckets(self, sym, buckets):
        if buckets:
            self.buckets[sym] = buckets
        else:
            del self.buckets[sym]

    def adjustWashSaleBucket(self, b, cb):
        ns = min(cb.nshares - cb.wash_shares, b.nshares)
        if ns <= 0:
            return None
        gain = cb.getGain()
        ws = math.ceil(100 * ns * (-gain - cb.wash_sale) /
                       (cb.nshares - cb.wash_shares)) * 0.01
        b2 = None
        if ns < b.nshares:
            b2 = copy.deepcopy(b)
            b2.nshares -= ns
            factor = ns / b.nshares
            adjustDividends(b2.dividends, 1 - factor)
            adjustDividends(b2.return_of_capital, 1 - factor)
            adjustDividends(b.dividends, factor)
            adjustDividends(b.return_of_capital, factor)
            b.nshares = ns
        b.dividends += [Dividend(d.date, d.amount * ns / cb.nshares)
                        for d in cb.dividends]
        b.purchase_date -= cb.end_date - cb.start_date
        b.share_adj += ws / ns
        cb.wash_sale += ws
        cb.wash_shares += ns
        return b2

    def adjustWashSaleAfter(self, buckets, completed):
        used_buckets = []
        for cb in completed:
            if cb.getGain() < 0:
                remaining_buckets = []
                for b in buckets:
                    if cb.end_date - b.purchase_date <= 30:
                        b2 = self.adjustWashSaleBucket(b, cb)
                        if b2:
                            remaining_buckets.append(b2)
                        used_buckets.append(b)
                    else:
                        remaining_buckets.append(b)
                buckets = remaining_buckets
        buckets += used_buckets
        buckets.sort(key=lambda b: b.purchase_date)
        return buckets

    def adjustWashSaleBefore(self, buckets, completed):
        b = buckets.pop()
        for cb in completed:
            b2 = self.adjustWashSaleBucket(b, cb)
            buckets.append(b)
            if b2:
                b = b2
            else:
                break
        buckets.sort(key=lambda b: b.purchase_date)
        # print([(str(b), Transaction.toDate(b.purchase_date)) for b in buckets])
        return buckets

    def sellShares(self, sym, count, share_price, share_expense, share_adj,
                   share_proceeds, date):
        buckets = self.buckets[sym]
        ncompleted = 0
        for b in buckets:
            amount, count = self.sellBucket(b, count, share_price,
                                            share_expense, share_adj,
                                            share_proceeds, date)
            if amount != 0:
                ncompleted += 1
            if count <= 0:
                break
        buckets = [b for b in buckets if b.nshares != 0]
        if ncompleted:
            buckets = self.adjustWashSaleAfter(
                buckets, self.completed_buckets[-ncompleted:])
        if count > 0.001:
            buckets.append(self.createBucket(sym, -count, share_price,
                                             share_expense, share_adj, date))
        self.updateBuckets(sym, buckets)

    def buyShares(self, sym, count, share_price, share_expense, share_adj,
                  date):
        buckets = self.buckets[sym]
        for b in buckets:
            amount, count = self.buyBucket(b, count, share_price,
                                           share_expense, share_adj, date)
            if count <= 0:
                break
        buckets = [b for b in buckets if b.nshares != 0]
        if count > 0.001:
            buckets.append(self.createBucket(sym, count, share_price,
                                             share_expense, share_adj, date))
            completed = [cb for cb in self.completed_buckets
                         if cb.symbol == sym and cb.end_date >= date - 30 and
                         cb.nshares - cb.wash_shares > 0 and cb.getGain() < 0]
            # if sym == 'AAPL120317C00540000':
            #     print(sym, count, share_price, share_expense, Transaction.toDate(date))
            #     print('completed', Transaction.toDate(date),
            #           [str(cb) for cb in completed])
            if completed:
                buckets = self.adjustWashSaleBefore(buckets, completed)
            # print('completed', Transaction.toDate(date),
            #       [str(cb) for cb in completed])
        self.updateBuckets(sym, buckets)

    def assignOption(self, option):
        if option.type == 'b':
            self.handleBuy(option)
            remaining = option.count
        else:
            self.handleSell(option)
            remaining = -option.count
        # for i in range(-3, 0):
        #     print(i, str(self.completed_buckets[i]))
        assigned = []
        while remaining != 0:
            cb = self.completed_buckets.pop()
            remaining += cb.nshares
            assigned.append(cb)
        assigned.reverse()
        self.assigned_buckets += assigned
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
        if option:
            # print('buy:', str(t), str(option))
            assigned = self.assignOption(option)
            for cb in assigned:
                sgn = math.copysign(1, cb.nshares)
                # end_share_price and end_share_expense are 0 for
                # assigned options
                share_adj = cb.start_share_price * sgn + cb.start_share_expense
                self.buyShares(t.name, cb.nshares * sgn, t.amount1,
                               share_expense, share_adj, t.date)
            # print('buy:', str(t), str(option))
            # for k, buckets in self.buckets.items():
            #     for b in buckets:
            #         print(str(b))
        elif t.count > 0:
            self.buyShares(t.name, t.count, t.amount1, share_expense,
                           0, t.date)
        amount = t.count * t.amount1 + t.amount2
        self.unrealized_total += amount
        self.cash -= amount
        if t.date == self.portfolio_date:
            self.cash_diff -= amount

    def handleSell(self, t, option=None):
        proceeds = t.count * t.amount1 - t.amount2
        share_expense = t.amount2 / t.count if t.count > 0 else 0
        if option:
            # print('sell:', str(t), str(option))
            assigned = self.assignOption(option)
            for cb in assigned:
                sgn = math.copysign(1, cb.nshares)
                share_adj = cb.start_share_price * sgn + cb.start_share_expense
                self.sellShares(t.name, cb.nshares * sgn, t.amount1,
                                share_expense, share_adj,
                                proceeds / (cb.nshares * sgn), t.date)
                # print(share_adj, str(cb))
        elif t.count > 0:
            self.sellShares(t.name, t.count, t.amount1, share_expense,
                            0, proceeds / t.count, t.date)
            # self.matchOption(t, future, basis)
        self.cash += proceeds
        if t.date == self.portfolio_date:
            self.cash_diff += proceeds
        basis = 0
        self.sales_total += proceeds

    def handleInterest(self, t, year):
        amount = t.amount1
        date = t.date
        self.cash += amount
        if date == self.portfolio_date:
            self.cash_diff += amount
        self.interest_total += amount
        self.year_dividend[year][t.name] += amount
        buckets = self.buckets[t.name]
        total_shares = sum(b.nshares for b in buckets if b.purchase_date < date)
        for b in buckets:
            if b.purchase_date < date:
                dividend = Dividend(date, amount * b.nshares / total_shares)
                if t.type == 'i':
                    b.dividends.append(dividend)
                else:
                    b.return_of_capital.append(dividend)
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
        for b in self.buckets[t.name]:
            total_shares += b.nshares
            total_cost += b.nshares * b.share_price + abs(b.nshares) * b.share_expense
            adjustDividends(b.dividends, (1 - t.amount2))
            adjustDividends(b.return_of_capital, (1 - t.amount2))
        proceeds = total_shares * t.amount1
        # amount2: fraction of transaction paid in cash
        total_value = total_shares * t.amount1 / t.amount2
        gain = total_value - total_cost
        if gain > proceeds:
          gain = proceeds
        elif gain < 0:
          gain = 0
        self.sales_total += proceeds
        if t.date == self.portfolio_date:
            self.equity_diff -= proceeds
        if gain > 0 and t.date >= self.bg_year:
            for b in self.buckets[t.name]:
              if t.date - b.purchase_date >= LONG_DAYS:
                  self.realized_long += gain * b.nshares / total_shares
              else:
                  self.realized_short += gain * b.nshares / total_shares
        if gain != proceeds:
            for b in self.buckets[t.name]:
                b.share_price += (gain - proceeds) / total_shares
        self.cash += proceeds
        if t.date == self.portfolio_date:
          self.cash_diff += proceeds

    def mergeBuckets(self, symbol, buckets):
        buckets2 = self.buckets[symbol]
        if buckets2:
            buckets2 += buckets
            buckets2.sort(key=lambda b: b.purchase_date)
        else:
            self.buckets[symbol] = buckets

    def handleChange(self, t):
        if t.amount1 > 0:
            self.handleCashConsideration(t)
        buckets = self.buckets[t.name]
        for b in buckets:
            b.symbol = t.name2
            b.nshares *= t.count
            b.share_price /= t.count
            b.share_expense /= t.count
            b.share_adj /= t.count
        if t.name2 != t.name:
            # Same names should really be handled by 'x'.
            self.mergeBuckets(t.name2, buckets)
            del self.buckets[t.name]
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
        new_buckets = []
        buckets = self.buckets[t.name]
        for b in buckets:
            expense1 = b.nshares * b.share_expense
            expense2 = value_fraction * expense1
            expense1 -= expense2
            adj1 = b.nshares * b.share_adj
            adj2 = value_fraction * adj1
            adj1 -= adj2
            nshares = b.nshares * t.amount1
            b.share_expense = expense1 / b.nshares
            b.share_adj = adj1 / b.nshares
            b.share_price *= 1 - value_fraction
            new_buckets.append(self.createBucket(
                t.name2, nshares, b.share_price * t.amount2,
                expense2 / nshares, adj2 / nshares, b.purchase_date))
        self.mergeBuckets(t.name2, new_buckets)

    def handleSplit(self, t):
        if t.name2 and t.name2 != t.name:
            self.handleSpinoff(t)
        else:
            # regular stock split
            fraction = 1 + t.amount1
            for b in self.buckets[t.name]:
                b.nshares *= fraction
                b.share_price /= fraction
                b.share_expense /= fraction
                b.share_adj /= fraction

    def handleDeposit(self, t):
      amount = t.amount1
      if t.date != self.portfolio_date:
          self.cash += amount
      if t.date == self.portfolio_date:
          self.new_deposits += amount
      else:
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

    def fillBuckets(self, transactions):
        year = 0
        year_end = 0
        for k, g in groupby(transactions, lambda t: t.date):
            # The transactions have to be kept in order other than matching
            # stocks with options.
            group = Portfolio.matchOptions(list(g))
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
        return sorted(set(s for k, v in self.buckets.items()
                          if v for s in getOptionPair(k)))

    def toDict(self, year=None, all=False):
        data = makeDict(self, ['cash', 'cash_diff', 'equity_diff'])
        keys = sorted(self.buckets)
        data['buckets'] = [b.toDict() for k in keys for b in self.buckets[k]]
        if all:
            cb = [b.toDict() for b in self.completed_buckets]
            data['completed_buckets'] = cb
            ab = [b.toDict() for b in self.assigned_buckets]
            data['assigned_buckets'] = ab
        elif year:
            year = int(year)
            start = Transaction.fromYear(year)
            end = Transaction.fromYear(year + 1)
            cb = [b.toDict() for b in self.completed_buckets
                  if b.end_date >= start and b.end_date < end]
            data['completed_buckets'] = cb
            data['dividend'] = self.year_dividend[year]
        return data


def main():
    files = []
    if sys.argv[1] == 'combined':
        for f in os.listdir('data'):
            if not f.endswith('~'):
                files.append(f)
        files.sort()
    else:
        files.append(sys.argv[1])
    date = Transaction.parseDate(sys.argv[2]) if len(sys.argv) > 2 else Transaction.today()
    portfolio = Portfolio(date)
    all_buckets = []
    for f in files:
        portfolio.account = f
        portfolio.fillBuckets(Transaction.readTransactions(os.path.join('data', f), date))
        all_buckets.append(portfolio.buckets)
        portfolio.emptyBuckets()
    portfolio.combineBuckets(all_buckets)
    # print(portfolio.getCurrentSymbols())
    # for k, buckets in portfolio.buckets.items():
    #     for b in buckets:
    #         print(str(b), getattr(b, 'account', None))


if __name__ == '__main__':
    main()
