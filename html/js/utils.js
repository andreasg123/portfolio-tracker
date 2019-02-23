export function makeCompletedBuckets(buckets, quotes, end_date) {
  return buckets.map(b => ({
    symbol: b.symbol,
    nshares: b.nshares,
    start_date: b.purchase_date,
    end_date,
    start_share_price: b.share_price,
    end_share_price: quotes[b.symbol],
    start_share_expense: b.share_expense,
    start_share_adj: b.share_adj,
    account: b.account
  }));
}

export function completeUnrealizedBuckets(buckets, quotes, completed_buckets) {
  completed_buckets.push(...makeCompletedBuckets(buckets, quotes));
}

export function getBucketTotal(b) {
  const amount = (b.nshares * (b.end_share_price || 0) -
                  Math.abs(b.nshares) *
                  ((b.end_share_adj || 0) + (b.end_share_expense || 0)));
  const basis = (b.nshares * (b.start_share_price || 0) +
                 Math.abs(b.nshares) *
                 ((b.start_share_adj || 0) + (b.start_share_expense || 0)));
  return {amount, basis, gain: amount - basis + (b.wash_sale || 0)}
}

export function collectSymbols(buckets) {
  const symbols = [];
  for (const b of buckets) {
    const opt = getOptionParameters(b.symbol);
    if (opt) {
      if (symbols.indexOf(opt[0]) < 0)
        symbols.push(opt[0]);
    }
    else if (symbols.indexOf(b.symbol) < 0)
      symbols.push(b.symbol);
  }
  symbols.sort();
  // console.log(symbols);
  return symbols;
}

export function groupBuckets(buckets) {
  const sym_map = new Map();
  for (const b of buckets) {
    let g = sym_map.get(b.symbol);
    if (!g) {
      g = [];
      sym_map.set(b.symbol, g);
    }
    g.push(b);
  }
  return sym_map;
}

export function getOptionParameters(symbol) {
  const m = symbol.match(/^(.*)(\d{6})([PC])(\d{8})$/);
  if (!m)
    return null;
  let sym = m[1];
  if (sym === 'BRKB')
    sym = 'BRK-B';
  else if (sym === 'VIX')
    sym = '^VIX';
  let date = m[2];
  date = '20' + date.substring(0, 2) + '-' + date.substring(2, 4) + '-' + date.substring(4);
  return [sym, date, m[3], 0.001 * m[4]];
}

export function normalizeDate(date) {
  const val = date.split('-');
  let year = Number(val[0]);
  if (year >= 1900)
    return date;
  year += 1900;
  if (year < 1970)
    year += 100;
  return year + '-' + val[1] + '-' + val[2];
}

export function toUSDate(iso_date) {
  const val = iso_date.split('-');
  return val[1] + '/' + val[2] + '/' + val[0].substring(2);
}

export function getUTC(date) {
  const val = date.split('-');
  return Date.UTC(val[0], val[1] - 1, val[2]);
}

export function isLong({nshares, start_date, end_date}) {
  return nshares > 0 && getDelta(start_date, end_date) >= 365;
}

export function getDelta(start, end) {
  return (getUTC(end) - getUTC(start)) / (3600000 * 24);
}

export function addDays(date, days) {
  const d = getUTC(date) + (days * 3600000 * 24);
  return new Date(d).toISOString().substring(0, 10);
}

export function formatDuration(days) {
  return days >= 365 ? (days / 365.25).toFixed(1) + 'y' : days.toFixed(0) + 'd';
}

export function formatCount(count) {
  const count_0 = count.toFixed(0);
  const count_2 = count.toFixed(2);
  return count_2 === count_0 + '.00' ? count_0 : count_2;
}

export function formatAmount(x, digits) {
  if (typeof x !== 'number')
    return x;
  if (typeof digits !== 'number')
    digits = 2;
  return x.toLocaleString(undefined, {minimumFractionDigits: digits,
                                      maximumFractionDigits: digits});
}
