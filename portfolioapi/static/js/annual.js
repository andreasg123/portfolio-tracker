import {
  formatAmount
} from './utils.js';
import {Polynomial} from './polynomial.js';
import {ServerError, StockSymbol} from './ui.js';
import {api_url_prefix} from './api-url.js';

const e = React.createElement;

let use_qqq = false;

function AccountHeader(props) {
  return e('tr', {},
           ...['Year', 'Deposits', 'Cash', 'Equity'].map(x => e('th', {}, x)),
           ...['1yr', '3yr', '5yr', '10yr'].map(x => e('th', {colSpan: 2}, x)));
}

function getYield(poly, equity, cash) {
  cash = cash || 0;
  let min_day = Number.MAX_VALUE;
  let max_day = 0;
  for (const e of poly.elements) {
    min_day = Math.min(min_day, e[1]);
    max_day = Math.max(max_day, e[1]);
  }
  if (equity === 0 && min_day > 0) {
    for (const e of poly.elements) {
      e[1] -= min_day;
    }
    max_day -= min_day;
  }
  min_day = 0;
  poly.append([-(equity + cash), 0]);
  const days = Math.min(365, max_day - min_day);
  // console.log('getYield', days, poly, Math.pow(poly.solve(), days));
  return days === 0 ? 1 : Math.pow(poly.solve(), days);
}

function AccountYear(props) {
  // console.log(props);
  const steps = [1, 3, 5, 10];
  const yields = [];
  // console.log(props.deposits);
  // console.log(props.year, props.start, props.end, props.prev_ends);
  for (const s of steps) {
    if (props.prev_totals.length < s)
      break;
    const prev_end = props.prev_ends[props.prev_ends.length - s];
    const days = Math.min(365, props.end - prev_end);
    const poly = new Polynomial();
    if (props.prev_totals[props.prev_totals.length - s] !== 0) {
      poly.append([props.prev_totals[props.prev_totals.length - s],
                   props.end - prev_end]);
    }
    for (const d of props.deposits) {
      if (d[0] > prev_end && d[0] <= props.end)
        poly.append([d[1], props.end - d[0]]);
    }
    // console.log(props.year, s, prev_end, props.end, poly.elements);
    const yield1 = e('td', {}, `${(100 * (getYield(poly, props.equity, props.cash) - 1)).toFixed(1)}%`);
    let yield2 = null;
    if (props.prev_index_quotes && props.prev_index_quotes.length >= s &&
        props.prev_index_quotes[props.prev_index_quotes.length - s]) {
      const index_poly = new Polynomial();
      index_poly.append([props.prev_index_quotes[props.prev_index_quotes.length - s],
                       props.end - prev_end]);
      for (const d of props.index_dividends) {
        if (d[0] > prev_end && d[0] <= props.end)
          index_poly.append([-d[1], props.end - d[0]]);
      }
      yield2 = e('td', {className: 'left small'},
                 `(${(100 * (getYield(index_poly, props.index_quote) - 1)).toFixed(1)}%)`);
    }
    else {
      yield2 = e('td', {});
    }
    yields.push(e(React.Fragment, {}, yield1, yield2));
  }
  const deposits = props.deposits.filter(x => x[0] >= props.start && x[0] <= props.end);
  return e('tr', {},
           e('td', {}, props.year),
           e('td', {}, formatAmount(deposits.reduce((sum, x) => sum + x[1], 0))),
           e('td', {}, formatAmount(props.cash)),
           e('td', {}, formatAmount(props.equity)),
           ...yields);
}

function AccountPerformance(props) {
  const prev_totals = [];
  const prev_ends = [];
  const prev_index_quotes = [];
  const years = [];
  for (const x of props.years.filter(x => x.year >= 1997)) {
    const quotes = props.quotes[x.year];
    let equity = 0;
    for (const lt of x.lots) {
      equity += lt.nshares * (quotes[lt.symbol] || 0);
    }
    const index_symbol = use_qqq ? 'QQQ' : 'SPY';
    const p = {year: x.year, start: x.start, end: x.end,
               cash: x.cash, equity, prev_totals: prev_totals.slice(),
               prev_ends: prev_ends.slice(),
               deposits: props.deposits,
               index_dividends: props.index_dividends[index_symbol]};
    const index_quote = quotes[index_symbol] || (use_qqq && quotes['QQQQ']);
    if (index_quote) {
      p.index_quote = index_quote;
      p.prev_index_quotes = prev_index_quotes.slice();
    }
    years.push(p);
    prev_totals.push(equity + x.cash);
    prev_ends.push(x.end);
    prev_index_quotes.push(index_quote);
  }
  return e(React.Fragment, {},
           e('a', {href: 'report.html?account=' + props.account},
             e('h3', {}, props.account)),
           e('table', {cellSpacing: 0},
             e('tbody', {},
               e(AccountHeader, props),
               ...years.map(x => e(AccountYear, x)))),
           e('p', {style: {marginTop: '2em'}}));
}

function TotalPerformance(props) {
  const keys = Object.keys(props.accounts);
  keys.sort();
  return e(React.Fragment, {},
           ...keys.map(k => e(AccountPerformance,
                              {quotes: props.quotes, index_dividends: props.index_dividends,
                               account: k,
                               ...props.accounts[k]})));
}

function renderError(data) {
  ReactDOM.render(e(ServerError, {error: data.error}),
                  document.getElementById('annual'));
}

function renderAnnual([data, names]) {
  // accounts are only needed for a TOC
  if (data.error) {
    renderError(data);
    return;
  }
  const year = data.year || new Date().getFullYear();
  document.title = `Annual Portfolio Performance for ${year}`;
  const props = data;
  ReactDOM.render(e(TotalPerformance, props),
                  document.getElementById('annual'));
}

async function loadData() {
  const urls = [`${api_url_prefix}get-annual${window.location.search}`,
                `${api_url_prefix}get-accounts`];
  const data = await Promise.all(urls.map(u => fetch(u).then(res => res.json())));
  renderAnnual(data);
}

loadData();
