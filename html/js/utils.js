export function makeCompletedLots(lots, quotes, end_date) {
  return lots.map(lt => ({
    symbol: lt.symbol,
    nshares: lt.nshares,
    start_date: lt.purchase_date,
    end_date,
    start_share_price: lt.share_price,
    end_share_price: quotes[lt.symbol],
    start_share_expense: lt.share_expense,
    start_share_adj: lt.share_adj,
    wash_days: lt.wash_days,
    account: lt.account
  }));
}

export function completeUnrealizedLots(lots, quotes, completed_lots) {
  completed_lots.push(...makeCompletedLots(lots, quotes));
}

export function getLotTotal(lt) {
  const amount = (lt.nshares * (lt.end_share_price || 0) -
                  Math.abs(lt.nshares) *
                  ((lt.end_share_adj || 0) + (lt.end_share_expense || 0)));
  const basis = (lt.nshares * (lt.start_share_price || 0) +
                 Math.abs(lt.nshares) *
                 ((lt.start_share_adj || 0) + (lt.start_share_expense || 0)));
  // wash sale is included in end_share_adj
  return {amount, basis, gain: amount - basis}
}

export function collectSymbols(lots) {
  const symbols = [];
  for (const lt of lots) {
    const opt = getOptionParameters(lt.symbol);
    if (opt) {
      if (symbols.indexOf(opt[0]) < 0)
        symbols.push(opt[0]);
    }
    else if (symbols.indexOf(lt.symbol) < 0)
      symbols.push(lt.symbol);
  }
  symbols.sort();
  // console.log(symbols);
  return symbols;
}

export function groupLots(lots) {
  const sym_map = new Map();
  for (const lt of lots) {
    let g = sym_map.get(lt.symbol);
    if (!g) {
      g = [];
      sym_map.set(lt.symbol, g);
    }
    g.push(lt);
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
  const options = {minimumFractionDigits: digits, maximumFractionDigits: digits};
  const s = x.toLocaleString(undefined, options);
  const zero = (0).toLocaleString(undefined, options);
  return s === '-' + zero ? zero : s;
}
