import {makeJSONRequest} from './xhr.js';
import {
  collectSymbols, completeUnrealizedBuckets, formatAmount, formatCount, getBucketTotal,
  getOptionParameters
} from './utils.js';
import {ServerError, StockSymbol} from './ui.js';

const e = React.createElement;

function OptionTocEntry(props) {
  const suffix = '\u00a0 ';     // '&nbsp; '
  if (props.selected)
    return e(React.Fragment, {}, e('b', {}, props.account), suffix);
  const url = `?account=${props.account}&date=${props.date}`;
  return e(React.Fragment, {}, e('a', {href: url}, props.account), suffix);
}

function OptionToc(props) {
  const y = new Date().getFullYear();
  const account_entries = props.accounts.map(a => e(OptionTocEntry, {
    account: a,
    date: props.date,
    selected: a === props.account}));
  const tax_url = `taxes.html?account=${props.account}`;
  return e(React.Fragment, {},
           ...account_entries,
           '\u2014 \u00a0',     // '&mdash; &nbsp;'
           e('a', {href: tax_url}, 'taxes'));
}

function OptionHeader() {
  const children = [];
  children.push(e('th', {className: 'left'}, 'symbol'));
  children.push(e('th', {}, '#'));
  children.push(e('th', {colSpan: 2}, 'date'));
  const columns = ['open', 'close', 'stock', 'gain', 'total'];
  children.push(...columns.map(c => e('th', {}, c)));
  return e('thead', {}, e('tr', {}, ...children));
}

function OptionGroup(props) {
  const info_url = 'http://finance.yahoo.com/quotes/';
  const children = [];
  let total = 0;
  for (let i = 0; i < props.buckets.length; i++) {
    const b = props.buckets[i];
    const row = [];
    const opt = getOptionParameters(b.symbol);
    let left_class = b.end_date ? 'left' : 'left unrealized';
    let small_class = b.end_date ? 'small' : 'small unrealized';
    let normal_class = b.end_date ? '' : 'unrealized';
    const group_end_class = 'group-end'
    if (i === props.buckets.length - 1) {
      left_class += ` ${group_end_class}`;
      small_class += ` ${group_end_class}`;
      normal_class += ` ${group_end_class}`;
    }
    row.push(e('td', {className: left_class},
               e(StockSymbol, {symbol: b.symbol, url: info_url + b.symbol})));
    row.push(e('td', {className: normal_class}, formatCount(b.nshares)));
    const date_props = ['start_date', 'end_date'];
    const amount_props = ['start_share_price', 'end_share_price'];
    row.push(...date_props.map(p => e('td', {className: small_class}, b[p] || '')));
    row.push(...amount_props.map(
      p => e('td', {className: small_class}, formatAmount(b[p] || 0))));
    let {amount, basis} = getBucketTotal(b);
    let stock = '';
    if (b.assigned) {
      stock = (props.historical_quotes[b.end_date][opt[0]] || 0) - opt[3];
      amount += stock * b.nshares * (opt[2] === 'C' ? 1 : -1);
      stock = formatAmount(stock);
    }
    total += amount - basis;
    row.push(e('td', {className: small_class}, stock));
    row.push(e('td', {className: normal_class}, formatAmount(amount - basis)));
    if (i === props.buckets.length - 1)
      row.push(e('td', {className: group_end_class}, formatAmount(total)));
    children.push(e('tr', {}, ...row));
  }
  return e(React.Fragment, {}, ...children);
}

function Options(props) {
  let symbols = collectSymbols(props.completed_buckets);
  const symbol_map = new Map();
  let prev = null;
  let group;
  let grand_total = 0;
  for (const s of symbols) {
    if (getOptionParameters(s))
      continue;
    for (const b of props.completed_buckets) {
      const opt = getOptionParameters(b.symbol);
      if (!opt || opt[0] !== s)
        continue;
      if (s !== prev) {
        prev = s;
        group = [];
        symbol_map.set(s, group);
      }
      let {amount, basis} = getBucketTotal(b);
      if (b.assigned) {
        const stock = (props.historical_quotes[b.end_date][opt[0]] || 0) - opt[3];
        amount += stock * b.nshares * (opt[2] === 'C' ? 1 : -1);
      }
      grand_total += amount - basis;
      group.push(b);
    }
  }
  symbols = Array.from(symbol_map.keys());
  symbols.sort();
  const groups = symbols.map(
    s => e(OptionGroup, {symbol: s, buckets: symbol_map.get(s),
                         historical_quotes: props.historical_quotes}));
  const cols = 9;
  return e('table', {cellSpacing: 0},
           e(OptionHeader),
           e('tbody', {},
             ...groups,
             e('tr', {},
               e('td', {colSpan: cols - 1}),
               e('td', {},
                 e('b', {}, formatAmount(grand_total))))));
}

function renderError(data) {
  ReactDOM.render(e(ServerError, {error: data.error}),
                  document.getElementById('options'));
}

function renderToc(account, date, accounts) {
  const container = document.getElementById('toc');
  ReactDOM.render(e(OptionToc, {account, date, accounts}), container);
}

function renderOptions([data, accounts]) {
  if (data.error) {
    renderError(data);
    return;
  }
  renderToc(data.account, data.date, [...accounts.accounts, 'combined']);
  data.assigned_buckets.forEach(ab => ab.assigned = true);
  data.completed_buckets.push(...data.assigned_buckets);
  data.completed_buckets.sort((a, b) => a.end_date.localeCompare(b.end_date));
  completeUnrealizedBuckets(data.buckets, data.quotes, data.completed_buckets);
  const props = {
    completed_buckets: data.completed_buckets,
    historical_quotes: data.historical_quotes
  };
  ReactDOM.render(e(Options, props), document.getElementById('options'));
}

const url = `/portfolioapi/get-options${window.location.search}`;
Promise.all([url, '/portfolioapi/get-accounts'].map(u => makeJSONRequest({method: 'GET', url: u})))
  .then(renderOptions);
