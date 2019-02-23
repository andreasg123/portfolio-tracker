import {makeJSONRequest} from './xhr.js';
import {
  collectSymbols, formatAmount, formatCount, formatDuration, getDelta,
  getOptionParameters, groupBuckets, normalizeDate
} from './utils.js';
import {Polynomial, testPolynomial} from './polynomial.js';
import {ServerError, StockSymbol} from './ui.js';

const e = React.createElement;

function SignedPercent(props) {
  if (!isFinite(props.factor) || Math.abs(props.factor) >= 100) {
    if (!props.neg_base === (props.factor < 0))
      return e('span', {className: 'neg'}, '-\u221e');
    else
      return e('span', {className: 'pos'}, '+\u221e');
  }
  const pct = toPercentString(props.factor, props.digits, props.neg_base);
  if (pct.charAt(0) === '+')
    return e('span', {className: 'pos'}, pct);
  else if (pct.charAt(0) === '-')
    return e('span', {className: 'neg'}, pct);
  else
    return pct;
}

function AccountTitle(props) {
  const {nshares, up_amount, down_amount, up_percent, down_percent} = getUpDownPercent(props);
  const title = props.title !== 'combined' ? props.title : '';
  if (!title && up_percent <= 0 && down_percent <= 0)
    return e(React.Fragment);
  const title_fraction = title ? 0.1 : 0;
  const title_cells = [];
  if (title_fraction)
    title_cells.push(e('td', {className: 'left', width: `${(100 * title_fraction).toFixed(0)}%`},
                       e('a', {href: `taxes.html?account=${title}`},
                         e('h3', {}, title))));
  if (up_percent > 0 || down_percent > 0) {
    const children = [];
    if (up_percent > 0)
      children.push(e('div', {className: 'up', style: {width: `${up_percent}%`}},
                      e('span', {className: 'tiny'}, '\u00a0'),
                      `${up_percent}% `,
                      e('span', {className: 'small'}, `+${formatAmount(up_amount, 0)}`)));
    if (up_percent + down_percent < 100)
      children.push(e('div', {className: 'unchanged',
                              style: {width: `${(100 - up_percent - down_percent)}%`}},
                      '\u00a0'));
    if (down_percent > 0)
      children.push(e('div', {className: 'down', style: {width: `${down_percent}%`}},
                      e('span', {className: 'tiny'}, '\u00a0'),
                      `${down_percent}% `,
                      e('span', {className: 'small'}, `-${formatAmount(down_amount, 0)}`)));
    title_cells.push(e('td', {className: 'left',
                              width: `${(100 * (1 - title_fraction)).toFixed(0)}%`},
                       ...children));
  }
  return e('tr', {},
           // with the nested table cells, one set has to lose its padding
           e('td', {style: {padding: 0}, className: 'left', colSpan: props.colspan},
             e('table', {width: '100%', cellSpacing: 0, cellPadding: 0},
               e('tbody', {},
                 e('tr', {}, ...title_cells)))));
}

function AccountHeader(props) {
  const info_url = 'http://finance.yahoo.com/quotes/';
  const symbols = props.buckets.map(b => b.symbol);
  const stocks = Array.from(new Set(symbols.filter(s => !getOptionParameters(s))));
  const options = Array.from(new Set(symbols.filter(s => getOptionParameters(s))));
  stocks.sort();
  options.sort();
  const columns = [['paid'], ['held'], ['last'], ['change'], ['value', {colSpan: 2}],
                   ['dividend', {colSpan: 2}], ['gain'], ['annual']];
  if (options.length)
    columns.push(['time']);
  return e('tr', {},
           e('th', {style: {textAlign: 'left'}},
             e('a', {href: info_url + stocks.join(',')}, 'stock'),
             ' / ',
             e('a', {href: info_url + options.join(',')}, 'option')),
           e('th', {},
             e('a', {className: 'expander', href: '', onClick: props.onClick},
               props.collapsed ? '+' : '-')),
           ...columns.map(c => e('th', c[1] || {}, c[0])));
}

function AccountGroup(props) {
  const render_symbol = in_the_money =>
        e('td', {className: `left${in_the_money ? ' money' : ''}`},
          e(StockSymbol,
            {symbol: props.symbol, url: props.url}));
  const {
    avg_days_held, avg_purchase_price, total_basis, total_shares, current_value,
    total_dividends, gain, yield1, yield2, in_the_money, time_value,
    quote, oldquote
  } = getGroupInfo(props.symbol, props.buckets, props.date,
                   props.quotes, props.oldquotes);
  const rows = [];
  let cols;
  if (props.collapsed || props.buckets.length === 1) {
    const count_props = props.buckets.length > 1 ? {className: 'mult'} : {};
    cols = [render_symbol(in_the_money),
            e('td', count_props, formatCount(total_shares)),
            e('td', count_props, avg_purchase_price.toFixed(3)),
            e('td', count_props, formatDuration(avg_days_held))];
  }
  else {
    for (let i = 0; i < props.buckets.length; i++) {
      const b = props.buckets[i];
      cols = [];
      if (i === 0)
        cols.push(render_symbol(in_the_money));
      else if (i === props.buckets.length - 1)
        cols.push(e('td', {}, `[${formatCount(total_shares)}]`));
      else
        cols.push(e('td', {}, '\u00a0'));
      const days_held = getDelta(b.purchase_date, props.date);
      cols.push(e('td', {}, formatCount(b.nshares)),
                e('td', {}, (b.share_price + (b.share_adj || 0)).toFixed(3)),
                e('td', {}, formatDuration(days_held)));
      if (i !== props.buckets.length - 1) {
        cols.push(e('td', {colSpan: props.has_options ? 9 : 8}, '\u00a0'));
        rows.push(e('tr', props.odd ? {className: 'odd'} : {}, ...cols));
      }
    }
  }
  cols.push(e('td', {}, quote.toFixed(3)));
  const quote_delta = quote - oldquote;
  if (quote_delta >= 0.0005)
    cols.push(e('td', {className: 'pos'}, `+${quote_delta.toFixed(3)}`));
  else if (quote_delta <= -0.0005)
    cols.push(e('td', {className: 'neg'}, quote_delta.toFixed(3)));
  else
    cols.push(e('td', {}, '0.000'));
  cols.push(e('td', {}, formatAmount(current_value)),
            e('td', {className: 'small'},
              `${(100 * current_value / props.equity).toFixed(0)}%`),
            e('td', {}, formatAmount(total_dividends)));
  // yield2 includes dividends
  cols.push(e('td', {className: 'small'},
              yield1 !== 0 && total_dividends !== 0 ?
              `${(100 * (Math.pow(yield2 / yield1, 365) - 1)).toFixed(1)}%` :
              '\u00a0'));
  cols.push(e('td', {}, e(SignedPercent, {factor: gain, digits: 1})));
  cols.push(e('td', {},
              yield2 !== 0 ?
              e(SignedPercent, {
                factor: Math.pow(yield2, 365), digits: 1,
                neg_base: total_shares < 0}) : '\u00a0'));
  if (props.has_options)
    cols.push(e('td', {className: 'small'},
                getOptionParameters(props.symbol) ?
                time_value.toFixed(2) : '\u00a0'));
  rows.push(e('tr', props.odd ? {className: 'odd'} : {}, ...cols));
  return e(React.Fragment, {}, ...rows);
}

function AccountFooter(props) {
  const  {cash, cash_diff, equity, equity_diff, put_hold} = getAccountInfo(props);
  const format_diff = (d, suffix) => {
    if (d === 0)
      return '\u00a0';
    let s = formatAmount(d);
    return `(${s.charAt(0) !== '-' ? '+' : ''}${s}${suffix || ''})`;
  };
  let total_suffix = '';
  if (equity + cash - equity_diff - cash_diff > 0)
    total_suffix = `; ${toPercentString((equity + cash) /
			                (equity + cash - equity_diff - cash_diff))}`;
  return e(React.Fragment, {},
           e('tr', {},
             e('td', {className: 'left total', colSpan: 5}, e('b', {}, 'Equity')),
             e('td', {className: 'total', colSpan: 2}, formatAmount(equity)),
             e('td', {className: 'left total', colSpan: props.has_options ? 6 : 5},
               format_diff(equity_diff))),
           e('tr', {},
             e('td', {className: 'left', colSpan: 5}, e('b', {}, 'Cash')),
             e('td', {colSpan: 2}, formatAmount(cash)),
             e('td', {className: 'left', colSpan: 2}, format_diff(cash_diff)),
             e('td', {className: 'left', colSpan: props.has_options ? 4 : 3},
               put_hold > 0 ? `(${formatAmount(put_hold)} locked)` : '\u00a0')),
           e('tr', {},
             e('td', {className: 'left total', colSpan: 5}, e('b', {}, 'Total Value')),
             e('td', {className: 'total', colSpan: 2},
               e('b', {}, formatAmount(equity + cash))),
             e('td', {className: 'left total', colSpan: props.has_options ? 6 : 5},
               format_diff(equity_diff + cash_diff, total_suffix))));
}

class AccountReport extends React.Component {
  constructor(props) {
    super(props);
    this.state = {collapsed: props.collapsed};
  }

  render() {
    const props = this.props;
    const info_url = 'http://finance.yahoo.com/quotes/';
    const has_options = props.buckets.some(b => getOptionParameters(b.symbol));
    const group_map = groupBuckets(props.buckets);
    const symbols = Array.from(group_map.keys());
    symbols.sort();
    const equity = props.buckets.reduce(
      (equity, b) => equity + (b.nshares * (props.quotes[b.symbol] || 0)), 0);
    const onClick = e => {
      e.preventDefault();
      e.stopPropagation();
      this.setState({collapsed: !this.state.collapsed});
    };
    const rows = [e(AccountTitle, {colspan: has_options ? 13 : 12, ...props}),
                  e(AccountHeader,
                    {collapsed: this.state.collapsed, onClick, ...props}),
                  ...symbols.map((s, i) => e(AccountGroup, {
                    collapsed: this.state.collapsed,
                    symbol: s,
                    url: info_url + s,
                    buckets: group_map.get(s),
                    odd: i % 2 !== 0,
                    date: props.date,
                    equity,
                    has_options,
                    quotes: props.quotes,
                    oldquotes: props.oldquotes
                  })),
                  e(AccountFooter, props)];
    return e('table', {cellSpacing: 0, style: {marginTop: '1em'}},
             e('tbody', {}, ...rows));
  }
}

function PortfolioReport(props) {
  const keys = Object.keys(props.accounts);
  keys.sort();
  const nav = [];
  const other_account = props.account === 'combined' ? 'all' : 'combined';
  const url = `?account=${other_account}` +
        (props.year ? `&year=${props.year}` : `&date=${props.date}`);
  nav.push(' \u00a0 ', e('span', {style: {fontSize: '80%', fontWeight: 'normal'}},
                         e('a', {href: url}, other_account)));
  return e(React.Fragment, {},
           e('h2', {style: {marginBottom: 0}},
             `Portfolio Report for ${props.year || props.date}`,
             ...nav),
           ...keys.map(k => e(AccountReport,
                              {title: k, date: props.date,
                               collapsed: true,
                               quotes: props.quotes, oldquotes: props.oldquotes,
                               ...props.accounts[k]})));
}

function getUpDownPercent({buckets, quotes, oldquotes}) {
  const result = {nshares: {}, up_amount: 0, down_amount: 0};
  let up_equity = 0;
  let down_equity = 0;
  let total_equity = 0;
  const symbols = collectSymbols(buckets);
  for (const s of symbols) {
    const total_shares = buckets.reduce(
      (count, b) => count + (b.symbol === s ? b.nshares : 0), 0);
    if (total_shares > 0) {
      const amount = total_shares * (quotes[s] || 0);
      total_equity += amount;
      const diff = (quotes[s] || 0) - (oldquotes[s] || 0);
      if (diff >= 0.0005) {
	up_equity += amount;
	result.up_amount += diff * total_shares;
      }
      else if (diff <= -0.0005) {
	down_equity += amount;
	result.down_amount -= diff * total_shares;
      }
    }
    result.nshares[s] = total_shares;
  }
  result.up_percent = Math.round(100 * up_equity / total_equity);
  result.down_percent = Math.round(100 * down_equity / total_equity);
  if (result.up_percent + result.down_percent > 100)
    result.down_percent = 100 - result.up_percent;
  return result;
}

function toPercentString(factor, digits, neg_base) {
  if (!isFinite(factor) || Math.abs(factor) >= 100)
    return `${!neg_base === (factor < 0) ? '-' : '+'}?????%`;
    factor -= 1;
    if (neg_base)
      factor = -factor;
  let change = `${formatAmount(100 * factor, digits)}%`;
  if (change === '0.00%' || change === '-0.00%')
    change = 'unch.';
  else if (change.charAt(0) !== '-')
    change = `+${change}`;
  return change;
}

function getGroupInfo(symbol, buckets, date, quotes, oldquotes) {
  const info = {
    avg_days_held: 0,
    avg_purchase_price: 0,
    total_dividends: 0,
    total_basis: 0,
    in_the_money: false,
    yield1: 0,
    yield2: 0
  };
  const opt = getOptionParameters(symbol);
  info.quote = quotes[symbol] || 0;
  info.oldquote = oldquotes[symbol] || 0;
  info.time_value = info.quote;
  if (opt) {
    const base_quote = quotes[opt[0]] || 0;
    const diff = (base_quote - opt[3]) * (opt[2] === 'P' ? -1 : 1);
    info.in_the_money = (diff > 0);
    if (info.in_the_money)
      info.time_value -= diff;
  }
  const poly = new Polynomial();
  info.total_shares = buckets.reduce((total, b) => total + b.nshares, 0);
  // For short positions, the gain is computed for negative values.
  // There shouldn't be any return of capital or dividends for short
  // positions because the security isn't owned.
  const sgn = Math.sign(info.total_shares);
  const last_date = buckets[buckets.length - 1].purchase_date;
  for (const b of buckets) {
    // Note that dividends and return of capital are not per share but
    // total amounts.
    if (b.dividends)
      info.total_dividends += b.dividends.reduce((total, d) => total + d.amount, 0);
    const basis = b.nshares * (b.share_price + (b.share_adj || 0)) +
          Math.abs(b.nshares) * (b.share_expense || 0);
    poly.append([sgn * basis, getDelta(b.purchase_date, date)]);
    let return_of_capital = 0;
    if (b.return_of_capital) {
      for (const r of b.return_of_capital) {
        return_of_capital += r.amount;
	poly.append([-sgn * r.amount, getDelta(r.date, date)]);
      }
    }
    info.total_basis += basis - return_of_capital;
    info.avg_purchase_price += b.nshares * b.share_price - return_of_capital;
    info.avg_days_held += b.nshares * getDelta(b.purchase_date, date);
  }
  info.avg_days_held /= info.total_shares;
  info.avg_purchase_price /= info.total_shares;
  info.current_value = info.total_shares * info.quote;
  if (Math.abs(info.current_value) > 0.0001 && date > last_date) {
    poly.append([-sgn * info.current_value, 0]);
    info.yield1 = poly.solve();
    // Do this after computing yield1.
    for (const b of buckets) {
      if (b.dividends)
        for (const d of b.dividends)
	  poly.append([-sgn * d.amount, getDelta(d.date, date)]);
    }
    info.yield2 = poly.solve();
  }
  info.gain = (info.current_value + info.total_dividends) / info.total_basis;
  if (info.total_shares < 0)
    info.gain = 2 - info.gain;
  return info;
}

function getAccountInfo({buckets, cash, cash_diff, equity_diff, quotes, oldquotes}) {
  let equity = 0;
  let put_hold = 0;
  for (const b of buckets) {
    const quote = quotes[b.symbol] || 0;
    const oldquote = oldquotes[b.symbol] || 0;
    equity += b.nshares * quote;
    equity_diff += b.nshares * (quote - oldquote);
    if (b.nshares < 0) {
      const opt = getOptionParameters(b.symbol);
      if (opt && opt[2] === 'P')
        put_hold += -b.nshares * opt[3];
    }
  }
  return {cash, cash_diff, equity, equity_diff, put_hold};
}

function renderError(data) {
  ReactDOM.render(e(ServerError, {error: data.error}),
                  document.getElementById('report'));
}

function renderReport([data, accounts]) {
  //testPolynomial();
  // accounts are only needed for a TOC
  if (data.error) {
    renderError(data);
    return;
  }
  const date = (data.year ? `${data.year}-12-31` :
                normalizeDate(data.date) || new Date().toISOString().substring(0, 10));
  document.title = `Portfolio Report for ${data.year || date}`;
  const props = {date: date, year: data.year, account: data.account,
                 accounts: data.accounts, quotes: data.quotes, oldquotes: data.oldquotes};
  ReactDOM.render(e(PortfolioReport, props), document.getElementById('report'));
}

const url = `/portfolioapi/get-report${window.location.search}`;
Promise.all([url, '/portfolioapi/get-accounts'].map(u => makeJSONRequest({method: 'GET', url: u})))
  .then(renderReport);
