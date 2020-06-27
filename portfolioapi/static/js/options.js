import {makeJSONRequest} from './xhr.js';
import {
  collectSymbols, completeUnrealizedLots, formatAmount, formatCount, getLotTotal,
  getOptionParameters
} from './utils.js';
import {ServerError, StockSymbol} from './ui.js';
import {api_url_prefix} from './api-url.js';

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
  for (let i = 0; i < props.lots.length; i++) {
    const lt = props.lots[i];
    const row = [];
    const opt = getOptionParameters(lt.symbol);
    let left_class = lt.end_date ? 'left' : 'left unrealized';
    let small_class = lt.end_date ? 'small' : 'small unrealized';
    let normal_class = lt.end_date ? '' : 'unrealized';
    const group_end_class = 'group-end'
    if (i === props.lots.length - 1) {
      left_class += ` ${group_end_class}`;
      small_class += ` ${group_end_class}`;
      normal_class += ` ${group_end_class}`;
    }
    row.push(e('td', {className: left_class},
               e(StockSymbol, {symbol: lt.symbol, url: info_url + lt.symbol})));
    row.push(e('td', {className: normal_class}, formatCount(lt.nshares)));
    const date_props = ['start_date', 'end_date'];
    const amount_props = ['start_share_price', 'end_share_price'];
    row.push(...date_props.map(p => e('td', {className: small_class}, lt[p] || '')));
    row.push(...amount_props.map(
      p => e('td', {className: small_class}, formatAmount(lt[p] || 0))));
    let {amount, basis} = getLotTotal(lt);
    let stock = '';
    if (lt.assigned) {
      stock = (props.historical_quotes[lt.end_date][opt[0]] || 0) - opt[3];
      amount += stock * lt.nshares * (opt[2] === 'C' ? 1 : -1);
      stock = formatAmount(stock);
    }
    total += amount - basis;
    row.push(e('td', {className: small_class}, stock));
    row.push(e('td', {className: normal_class}, formatAmount(amount - basis)));
    if (i === props.lots.length - 1)
      row.push(e('td', {className: group_end_class}, formatAmount(total)));
    children.push(e('tr', {}, ...row));
  }
  return e(React.Fragment, {}, ...children);
}

function Options(props) {
  let symbols = collectSymbols(props.completed_lots);
  const symbol_map = new Map();
  let prev = null;
  let group;
  let grand_total = 0;
  for (const s of symbols) {
    if (getOptionParameters(s))
      continue;
    for (const lt of props.completed_lots) {
      const opt = getOptionParameters(lt.symbol);
      if (!opt || opt[0] !== s)
        continue;
      if (s !== prev) {
        prev = s;
        group = [];
        symbol_map.set(s, group);
      }
      let {amount, basis} = getLotTotal(lt);
      if (lt.assigned) {
        const stock = (props.historical_quotes[lt.end_date][opt[0]] || 0) - opt[3];
        amount += stock * lt.nshares * (opt[2] === 'C' ? 1 : -1);
      }
      grand_total += amount - basis;
      group.push(lt);
    }
  }
  symbols = Array.from(symbol_map.keys());
  symbols.sort();
  const groups = symbols.map(
    s => e(OptionGroup, {symbol: s, lots: symbol_map.get(s),
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
  data.assigned_lots.forEach(lt => lt.assigned = true);
  data.completed_lots.push(...data.assigned_lots);
  data.completed_lots.sort((a, b) => a.end_date.localeCompare(b.end_date));
  completeUnrealizedLots(data.lots, data.quotes, data.completed_lots);
  const props = {
    completed_lots: data.completed_lots,
    historical_quotes: data.historical_quotes
  };
  ReactDOM.render(e(Options, props), document.getElementById('options'));
}

const urls = [`${api_url_prefix}get-options${window.location.search}`,
              `${api_url_prefix}get-accounts`];
Promise.all(urls.map(u => makeJSONRequest({method: 'GET', url: u})))
  .then(renderOptions);
