Import from Brokerage Accounts
==============================

There are several scripts that can convert transactions downloaded from
brokerage firms.  Downloads from other firms may be submitted as issues for
possible creation of additional conversion scripts.


Charles Schwab
--------------

The script [import-schwab.py](./import-schwab.py) converts transactions
downloaded from Charles Schwab brokerage accounts.  Downloads are limited to the
last four years so that earlier transactions have to be entered manually.

There is insufficient data to determine the factor of a stock split.  The
corresponding transaction is converted to a comment (starting with `#`).  After
adding the factor, the transaction may be uncommented.  There is also
insufficient information for spin-offs and cash in lieu of fractional shares.
The comments in those transactions indicate the missing data.

Transfers from another brokerage account are also commented out.  To maintain
history, it is better to maintain the other brokerage account separately up to
the time of transfer and to mark the transfer.  This assumes a complete
transfer.


Fidelity
--------

The script [import-fidelity-401k.py](./import-fidelity-401k.py) converts
transactions downloaded from Fidelity 401(k) accounts.  The use of the site
[401k.fidelity.com](https://401k.fidelity.com/) is recommended because it
allows for a single download of the last ten years.  The main Fidelity site
only supports downloads of 90 days at a time for the last five years.

For different employers, Fidelity uses different actions in the download,
sometimes only differing in capitalization, other times using different terms
for the same action.  That makes it likely that the script would need to be
modified for another employer.

Fidelity does not provide mutual fund symbols in the download.  The script
contains mappings for several funds but more may need to be added.

Some funds are internal to an employer such that quotes cannot be downloaded
from sites such as Yahoo.  For example, the fund `PIMCO Total Return` has the
internal symbol
[TPG6](https://workplaceservices.fidelity.com/mybenefits/workplacefunds/summary/TPG6)
and not the public symbol [PTTRX](https://finance.yahoo.com/quote/PTTRX).  The
latter has a completely different price, in part because it doesn't keep the
dividend.  Keeping the reported fund name in the converted transactions is the
best choice because the stock quote retrieval ignores symbols containing
spaces.  It is recommended to manually add a quote from the statements at least
once per quarter such that the chart approximates the actual performance.

The script
[import-fidelity-brokeragelink.py](./import-fidelity-brokeragelink.py) converts
transactions downloaded from Brokeragelink.  Unfortunately, the 90-day limit
per download applies.  The script takes any number of file names as parameters
but those need to be in chronological order.  It is recommended to make the
alphabetical order of the downloaded files match the chronological order, e.g.,
by appending year and start month at the end of each file name.  Otherwise, the
script is straightforward and no manual adjustments should be needed.


Quicken
-------

Stock quotes may be imported from Quicken.  Both CSV and QIF format can be
read by the script [import-quotes-quicken.py](./import-quotes-quicken.py):

    ./import-quotes-quicken.py security1.qif security2.qif

The subdirectory `quotes` will be used to store the quote files.  This should
be symlinked to the correct location described by the variable `quote_dir` in
[stockquotes.py](../portfolioapi/stockquotes.py).  Dates for which the quote
file exists before the import is started will be ignored.  To import all data,
existing quote files should be deleted first.

After stock quotes are imported, the quote database needs to be updated by
accessing the URL `/update-quotes`.
