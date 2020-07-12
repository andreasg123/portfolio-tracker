Format of Account Files
=======================

Each line in a file describes a transaction.  Text after `#`,
either on a separate line or at the end of a line, is a comment.
Fields in a line are separated by a vertical bar `|`.  The first three fields
are always the same: a date in ISO format, a one-character action, and a stock
symbol or other name.

    1999-04-19|b|QQQ|100|99.75|29.95

Examples can be found among the [tests](../tests/data/account2).


Types of Actions
----------------

* Deposit (`d`): Deposits or withdraws funds for the account.  The name is a memo
  for the purpose and may just be `Deposit`.  The fourth field is the amount with
  a positive value for deposit and a negative value for a withdrawal.

      1998-12-21|d|Deposit|278000

* Buy (`b`), Sell (`s`): The additional fields are: the number of shares, the share
  price, and the total fee.  For buying, the fee is added to the total amount.
  For selling, the fee is subtracted from the total amount.  In this example,
  100 shares of `QQQ` were bought for $99.75 per share with a fee of $29.95.

      1999-04-19|b|QQQ|100|99.75|29.95

  Short sales sell an equity without having a holding of it.

* Interest (`i`): This is either the dividend for a holding, interest on the cash
  balance, or negative margin interest.  For dividends, the stock symbol is in
  the third field.  For interest, a different name such as `Margin` should be
  used.  There is no means to specify the number of shares, only the total
  amount.  The dividend will be allocated to the current holdings.

      2019-11-08|i|MA|33

* Return of capital (`r`): This is similar to a one-time dividend but the
  treatment for tax purposes is different.

* Split (`x`): The fourth field represents the number of additional shares for
  each share of the stock.  In a 3-for-1 split, that number is `2`.  For a
  reverse split, that number is negative, e.g., `-0.9` for a 1-for-10 reverse
  split.  The same action can also represent a spin-off where the new symbol is
  in the fifth field and the ratio of the share prices of the new and original
  stock at the spin-off date is in the sixth field.  A spin-off or reverse
  split may be followed by a sale to capture the cash-in-lieu of fractional
  shares.
  
      2000-03-20|x|QQQ|1
      2000-09-29|x|LU|0.0833333|AV|0.6472
      2000-09-29|s|AV|0.66666|15.555|0

* Change (`c`): Indicates the change of a stock symbol.  Unlike a spin-off, no
  holdings of the original symbol remain.  The fourth field is the number of
  shares received for each share of the original stock and the fifth field is the
  new symbol.  If part of the transaction was in cash, the sixth field contains
  the cash per share and the seventh field is the fraction of the transaction paid
  in cash.  Note that a change may also happen to an option if the underlying
  stock splits.

      1997-08-15|c|NYN|0.768|BEL
      2010-01-04|c|MVL|0.7452|DIS|30|0.5552193394
      2012-07-23|c|CME121222P00280000|5|CME121222P00056000

  While this can represent a stock split without a change of symbol (by using
  the same symbol twice), the recommendation is to use `x` instead even though `x`
  involves slightly more complicated math for reverse splits.  For any split, just
  subtract `1` from the number that would be used for a change. For example, `0.25`
  is replaced by `-0.75` in a 1-for-4 reverse split.
