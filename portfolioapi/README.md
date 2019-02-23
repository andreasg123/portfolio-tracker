# Portfolio Tracker

## Data Files

Each account is represented by a text file in the directory `data`. The file name is the account name for display and access.

Each transaction is on a single line in the text file with parameters separated by a vertical bar (|).  The first three parameters always have the same meaning.  `date` is in ISO format, either with 2 or 4-digit year, `op` is a one-character code, and `name` is the identifier for the security or other entity.

```
date|op|name
```


### Operations

#### Buy or Sell, b, s

This represents buying or selling a security, including short-selling and closing short positions.  The additional parameters are (`share-price` and `expense` are optional):

```
count|share-price|expense
```

When options expire or are assigned, the share price and expense are zero.  Expiration is not handled automatically but needs to be recorded.  A stock transaction caused by an option assignment needs to be recorded on the same day.


#### Interest, i, r

This represents stock dividends with the exception of `r` that is a return on capital.  The additional parameter is:

```
interest
```

Note that return of capital is not considered a taxable event but reduces the cost basis: https://www.investopedia.com/terms/r/returnofcapital.asp


#### Extra shares, x

This represents stock splits and spin-offs.  The parameter `extra-shares` indicates how many new shares are issued for each existing share, e.g., 2 for a 3:1 split.  For reverse splits, this number is negative, e.g., -0.9 for a 1:10 reverse split.  Optionally, this may represent a spin-off of a new security `new-name`.  `ratio-new-old-price` represents the ratio of the closing prices of the new and old securities at the end of the trading day. Ratios should be recorded with at least 10 fractional digits to make sure that, even for large amounts, cents are computed correctly.

```
split-factor|extra-shares|new-name|ratio-new-old-price
```


#### Change, c

This represents a security rename.  An optional adjustment of the number of shares is represented by `new-fraction` (1 for no change in count).  Only a single security remains.  Optionally, this may include a cash portion represented by the optional parameters `cash-per-share` and `cash-fraction`.  Additional parameters:

```
new-name|new-fraction|cash-per-share|cash-fraction
```


#### Deposit, d

This represents deposits to and withdrawals from the account.  Additional parameters:

```
name|amount
```

### Examples

ABC has a 3:1 split. For each share, two additional shares of ABC are issued.  There are also open options with a strike price of $150.  After the split, there are three times as many options with a strike price of $50.

```
2018-12-31|x|ABC|2
2018-12-31|c|ABC190118P00150000|ABC190118P00050000|3
```

In a merger, each share of ABC is converted into 0.1 shares of XYZ. 105 shares of ABC were in the account.  Cash in lieu of fraction shares for 0.5 shares of XYZ amounted to $10.  That corresponds to a share price of $20. The remaining 10 shares of XYZ stay in the account.

```
2018-11-30|c|ABC|XYZ|0.1
2018-12-01|s|XYZ|0.5|20|0
```

In a spinoff, each share of HPE [received 0.085904 shares of DXC](https://investors.hpe.com/~/media/Files/H/HP-Enterprise-IR/documents/everett-6045B-statement-form8937-04-26-2017.pdf).  Afterwards, DXC traded at $67.95 and HPE at $13.63 (ratio 4.985). The account held 126 shares of HPE.  0.823904 shares of DXC sold for $56.62, $68.72 per share.

```
2017-03-31|x|HPE|0.085904|DXC|4.9853264857
2017-03-31|s|DXC|0.823904|68.7215986329
```

In an acquisition, each share of MVL received $30 and 0.7452 shares of DIS. The price of DIS after the merger was $32.25, or $24.03 per share of MVL. That makes the cash portion 55.5% of the total (30 / (30 + 24.03)).  The account held 500 shares of MVL, resulting in $15,000 and 372.6 shares of DIS.  Cash in lieu of 0.6 fractional shares was $19.35.

```
2010-01-04|c|MVL|DIS|0.7452|30|0.5552193394
2010-01-04|s|DIS|0.6|32.25|0
```

A put option for AMD is assigned.  This is recorded as a purchase of the put for $0 and a purchase of the stock on the same date for the strike price of $26.  The count for the option is the same as for the stock and not the number of lots of 100.

```
2018-10-30|b|AMD181123P00026000|200|0|0
2018-10-30|b|AMD|200|26|4.95
```


## Web API

There are several end points that return JSON data.


## get-accounts

Returns the names of all available accounts by listing all files in the `data` directory, ignoring files starting with `.` or ending with `~`.

```
{"accounts": ["account-1", "account-2", "account-3"]}
```


## get-taxes?account=abc&year=1999

Returns the tax information for the account specified with the `account` parameter (default: `ag-broker`) and the year specified with the `year` parameter (default: *current year*).  The special account name `combined` returns the combined information for all accounts.

`completed_buckets` represents all holdings that were closed during the specified year.  `buckets` represents all holdings that were open at the end of the specified year.  `quotes` contains the stock quotes for the end of the year.  `share_adj` represents the adjustments per share for buying or selling stock via an assigned option.  `share_expense` represents the fees per share for buying or selling securities.  A negative value for `nshares` indicates that this was a short position.


```
{
  "account": "abc",
  "year": "1999",
  "completed_buckets": [
    {
      "symbol": "NVDA190111P00115000",
      "nshares": -200.0,
      "start_share_price": 3.1,
      "end_share_price": 0.1,
      "start_share_expense": 0.03145,
      "end_share_expense": 0.0314,
      "start_date": "2018-12-27",
      "end_date": "2019-01-04"
    },
    {
      "symbol": "MA190125P00185000",
      "nshares": -300.0,
      "start_share_price": 3.5,
      "end_share_price": 2.82,
      "start_share_expense": 0.02313333,
      "end_share_expense": 0.0231,
      "start_date": "2019-01-08",
      "end_date": "2019-01-08"
    }
  ],
  "buckets": [
    {
      "symbol": "AAPL",
      "nshares": 700.0,
      "share_price": 1.48214286,
      "share_expense": 0.01069643,
      "share_adj": 0.0,
      "purchase_date": "2000-10-10",
      "dividends": [
        {"date": "2012-08-16", "amount": 265.0},
        {"date": "2012-11-15", "amount": 265.0}
      ]
    },
    {
      "symbol": "OTEX",
      "nshares": 400.0,
      "share_price": 15.0,
      "share_expense": 0.022375,
      "share_adj": -0.650725,
      "purchase_date": "2012-03-17",
      "dividends": [
        {"date": "2013-06-21", "amount": 25.5},
        {"date": "2013-09-20", "amount": 25.5}
      ]
    }
  ],
  "quotes": {
    "AAPL": 152.29,
    "AMD": 20.27
  }
}
```

## get-options?account=abc&date=1999-01-23

Most of the information is the same as that returned by `get-taxes` but up to a specific date instead of the end of a year.  In addition, `assigned_buckets` contains information about assigned options in the same format as `completed_buckets`.  `end_share_price` and `end_share_expense` are always zero.  Each assigned bucket has a corresponding `share_adj` in in `completed_buckets` or `buckets` for stock holdings.  Here, the information is provided separately to see performance of all options and not just the unassigned ones.  `historial_quotes` contains stock quotes for all days when options were assigned to allow for a comparison between strike price and trade price.

```
{
  "account": "abc",
  "date": "1999-01-23",
  "completed_buckets": [...],
  "buckets": [...],
  "assigned_buckets": [
    {
      "symbol": "ROC110820P00050000",
      "nshares": -100.0,
      "start_share_price": 2.85,
      "end_share_price": 0.0,
      "start_share_expense": 0.0971,
      "end_share_expense": 0.0,
      "start_date": "2011-06-03",
      "end_date": "2011-08-22"
    },
    {
      "symbol": "SPY111119C00120000",
      "nshares": -100.0,
      "start_share_price": 4.67,
      "end_share_price": 0.0,
      "start_share_expense": 0.0971,
      "end_share_expense": 0.0,
      "start_date": "2011-10-12",
      "end_date": "2011-11-19"
    }
  ],
  "quotes": {...},
  "historical_quotes": {
    "2011-11-19": {
      "A": 36.81,
      "AAPL": 374.94
    },
    "2016-07-15": {
      "AAPL": 98.78,
      "ADSK": 57.98
    }
  }
}  
```


# get-report?account=all&date=1999-01-23

Returns information on the specified date for one or more accounts.  The special account `all` (default) returns information for all accounts separately.  The special account `combined` combines the information for all accounts.  `cash_diff` represents the change in cash on the specified date due to transactions on that date.  `equity_diff` represents the same for equities.  `oldquotes` contains quotes for the previous trading day intended to compute an additional difference in equity due to change in value.


```
{
  "account": "all"
  "date": "1999-01-23",
  "accounts": {
    "abc": {
      "cash": 405671.6698945,
      "cash_diff": 1124.14,
      "equity_diff": -960.0,
      "buckets": [...]
    }
  },
  "quotes": {...},
  "oldquotes": {
    "AAPL": 147.93,
    "AMD": 20.57
  }
}
```
