import {makeJSONRequest} from './xhr.js';
import {
  collectSymbols, formatAmount, formatCount, formatDuration, getDelta,
  getOptionParameters, groupLots, normalizeDate, getUTC
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
  const symbols = props.lots.map(lt => lt.symbol);
  const stocks = Array.from(new Set(symbols.filter(s => !getOptionParameters(s))));
  const options = Array.from(new Set(symbols.filter(s => getOptionParameters(s))));
  stocks.sort();
  options.sort();
  let columns = [['paid'], ['held'], ['last'], ['change'], ['value', {colSpan: 2}],
                 ['dividend', {colSpan: 2}], ['gain'], ['annual'], ['ytd']];
  if (options.length)
    columns.push(['time']);
  columns = columns.map(c => {
    const onClick = e => props.onSort(e, c[0]);
    return e('th', c[1] || {},
      e('a', {className: 'expander', href: '', onClick}, c[0]));
  });
  return e('tr', {},
           e('th', {style: {textAlign: 'left'}},
             e('a', {href: info_url + stocks.join(',')}, 'stock'),
             ' / ',
             e('a', {href: info_url + options.join(',')}, 'option')),
           e('th', {},
             e('a', {className: 'expander', href: '', onClick: props.onCollapse},
               props.collapsed ? '+' : '-')),
           ...columns);
}

function AccountGroup(props) {
  // console.log('AccountGroup', props.yearquotes);
  const render_symbol = in_the_money =>
        e('td', {className: `left${in_the_money ? ' money' : ''}`},
          e(StockSymbol,
            {symbol: props.symbol, url: props.url}));
  const {
    avg_days_held, avg_purchase_price, total_basis, total_shares, current_value,
    total_dividends, gain, yield1, yield2, ytd, in_the_money, time_value,
    quote, oldquote, yearquote
  } = getGroupInfo(props.symbol, props.lots, props.date,
                   props.quotes, props.oldquotes, props.yearquotes);
  const rows = [];
  let cols;
  if (props.collapsed || props.lots.length === 1) {
    const count_props = props.lots.length > 1 ? {className: 'mult'} : {};
    cols = [render_symbol(in_the_money),
            e('td', count_props, formatCount(total_shares)),
            e('td', count_props, avg_purchase_price.toFixed(3)),
            e('td', count_props, formatDuration(avg_days_held))];
  }
  else {
    for (let i = 0; i < props.lots.length; i++) {
      const lt = props.lots[i];
      cols = [];
      if (i === 0)
        cols.push(render_symbol(in_the_money));
      else if (i === props.lots.length - 1)
        cols.push(e('td', {}, `[${formatCount(total_shares)}]`));
      else
        cols.push(e('td', {}, '\u00a0'));
      const days_held = getDelta(lt.purchase_date, props.date) + lt.wash_days;
      let return_of_capital = 0;
      if (lt.return_of_capital) {
        for (const r of lt.return_of_capital) {
          return_of_capital += r.amount;
        }
        return_of_capital /= lt.nshares;
      }
      cols.push(e('td', {}, formatCount(lt.nshares)),
                e('td', {}, (getAdjustedPrice(lt) - return_of_capital).toFixed(3)),
                e('td', {}, formatDuration(days_held)));
      if (i !== props.lots.length - 1) {
        cols.push(e('td', {colSpan: props.has_options ? 10 : 9}, '\u00a0'));
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
  cols.push(e('td', {},
              ytd !== 0 ?
              e(SignedPercent,
                {factor: ytd, digits: 1, neg_base: total_shares < 0}) :
              '\u00a0'));
  if (props.has_options)
    cols.push(e('td', {className: 'small'},
                getOptionParameters(props.symbol) ?
                time_value.toFixed(2) : '\u00a0'));
  rows.push(e('tr', props.odd ? {className: 'odd'} : {}, ...cols));
  return e(React.Fragment, {}, ...rows);
}

function AccountFooter(props) {
  // console.log('AccountFooter', props);
  const {cash, cash_diff, cash_like, cash_like_diff, equity,
         equity_diff, new_deposits, put_hold} = getAccountInfo(props);
  const format_diff = (d, suffix) => {
    if (d === 0)
      return '\u00a0';
    let s = formatAmount(d);
    return `(${s.charAt(0) !== '-' ? '+' : ''}${s}${suffix || ''})`;
  };
  const total_value = equity + cash + cash_like;
  const total_diff = cash_diff + cash_like_diff + equity_diff;
  let total_suffix = '';
  if (equity + cash - equity_diff - cash_diff > 0)
    total_suffix = `; ${toPercentString(total_value / (total_value - total_diff))}`;
  const colSpan = props.has_options ? 5 : 4;
  const rows = [
    e('tr', {},
      e('td', {className: 'left total', colSpan: 5}, e('b', {}, 'Equity')),
      e('td', {className: 'total', colSpan: 2}, formatAmount(equity)),
      e('td', {className: 'left total', colSpan: colSpan + 2},
        format_diff(equity_diff))),
    e('tr', {},
      e('td', {className: 'left', colSpan: 5}, e('b', {}, 'Cash')),
      e('td', {colSpan: 2}, formatAmount(cash)),
      e('td', {className: 'left', colSpan: 2}, format_diff(cash_diff)),
      e('td', {className: 'left', colSpan},
        put_hold > 0 ? `(${formatAmount(put_hold)} cash secured put requirement)` : '\u00a0')),
  ];
  if (cash_like) {
    rows.push(e('tr', {},
                e('td', {className: 'left', colSpan: 5}, e('b', {}, 'Money Market')),
                e('td', {colSpan: 2}, formatAmount(cash_like)),
                e('td', {className: 'left', colSpan: 2}, format_diff(cash_like_diff)),
                e('td', {className: 'left', colSpan}, '\u00a0')));
  }
  rows.push(e('tr', {},
             e('td', {className: 'left total', colSpan: 5}, e('b', {}, 'Total Value')),
             e('td', {className: 'total', colSpan: 2},
               e('b', {}, formatAmount(total_value))),
             e('td', {className: 'left total', colSpan: colSpan + 2},
               format_diff(total_diff, total_suffix))));
  if (new_deposits) {
    rows.push(e('tr', {},
                e('td', {className: 'left', colSpan: 5}, e('b', {}, 'New Deposits')),
                e('td', {colSpan: 2}, formatAmount(new_deposits))));
  }
  return e(React.Fragment, {}, ...rows);
}

function AccountReport(props) {
  const [collapsed, setCollapsed] = React.useState(props.collapsed);
  const [sort, setSort] = React.useState('symbol');
  const {
    lots,
    date,
    quotes,
    oldquotes,
    yearquotes
  } = props;
  const info_url = 'http://finance.yahoo.com/quotes/';
  const has_options = lots.some(lt => getOptionParameters(lt.symbol));
  const group_map = groupLots(lots);
  const entries = Array.from(group_map.entries());
  let cmp;
  switch (sort) {
  case 'value':
    cmp = (a, b) => getSortValue(b[0], b[1], quotes) -
      getSortValue(a[0], a[1], quotes);
    break;
  case 'dividend':
    cmp = (a, b) => getSortDividend(b[0], b[1], date, quotes, oldquotes) -
      getSortDividend(a[0], a[1], date, quotes, oldquotes);
    break;
  case 'gain':
    cmp = (a, b) => getSortGain(b[0], b[1], date, quotes, oldquotes) -
      getSortGain(a[0], a[1], date, quotes, oldquotes);
    break;
  case 'annual':
    cmp = (a, b) => getSortAnnual(b[0], b[1], date, quotes, oldquotes) -
      getSortAnnual(a[0], a[1], date, quotes, oldquotes);
    break;
  case 'ytd':
    cmp = (a, b) => getSortYtd(b[0], b[1], date, quotes, oldquotes, yearquotes) -
      getSortYtd(a[0], a[1], date, quotes, oldquotes, yearquotes);
    break;
  default:
    cmp = (a, b) => a[0].localeCompare(b[0]);
    break;
  }
  entries.sort(cmp);
  const equity = lots.reduce(
    (equity, lt) => equity + (lt.nshares * (quotes[lt.symbol] || 0)), 0);
  const onCollapse = e => {
    e.preventDefault();
    e.stopPropagation();
    setCollapsed(!collapsed);
  };
  const onSort = (e, new_sort) => {
    console.log('onSort', new_sort, e);
    e.preventDefault();
    e.stopPropagation();
    setSort(new_sort);
  }
  const rows = [e(AccountTitle, {colspan: has_options ? 14 : 13, ...props}),
                e(AccountHeader,
                  {collapsed: collapsed, onCollapse, onSort, ...props}),
                ...entries.map((s, i) => e(AccountGroup, {
                  collapsed,
                  symbol: s[0],
                  url: info_url + s,
                  lots: s[1],
                  odd: i % 2 !== 0,
                  date: date,
                  equity,
                  has_options,
                  quotes,
                  oldquotes,
                  yearquotes
                })),
                e(AccountFooter, {has_options, ...props})];
  return e('table', {cellSpacing: 0, style: {marginTop: '1em'}},
           e('tbody', {}, ...rows));
}

function PortfolioReport(props) {
  const keys = Object.keys(props.accounts);
  keys.sort();
  const nav = [];
  const other_account = props.account === 'combined' ? 'all' : 'combined';
  nav.push(' \u00a0 ',
           e('a',
             {href: `?account=${other_account}` +
              (props.year ? `&year=${props.year}` : `&date=${props.date}`)},
             other_account));
  if (props.year) {
    for (let i = -1; i <= 1; i += 2) {
      const other_year = (Number(props.year) + i).toString();
      nav.push(' \u00a0 ',
               e('a', {href: `?account=${props.account}&year=${other_year}`}, other_year));
    }
  }
  else {
    const d = new Date(getUTC(props.date));
    for (let i = -1; i <= 1; i += 2) {
      let other_date;
      if (i === -1) {
        other_date = Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), 0);
      }
      else {
        other_date = Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 0);
        if (other_date === d.getTime()) {
          other_date = Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 2, 0);
        }
      }
      other_date = new Date(other_date).toISOString().substring(0, 10);
      nav.push(' \u00a0 ',
               e('a', {href: `?account=${props.account}&date=${other_date}`}, other_date));
    }
  }
  const reports = keys.map(k => e(AccountReport, {
    title: k, date: props.date,
    collapsed: true,
    quotes: props.quotes, oldquotes: props.oldquotes,
    yearquotes: props.yearquotes,
    ...props.accounts[k]
  }));
  return e(React.Fragment, {},
           e('div', {style: {display: 'flex',
                             justifyContent: 'space-between',
                             marginTop: '1em'}},
             e('h2', {style: {margin: 0}},
               `Portfolio Report for ${props.year || props.date}`,
               e('span', {style: {fontSize: '80%', fontWeight: 'normal'}},
                 ...nav)),
             e('a', {href: '/portfolioapi/retrieve-quotes?force=true'}, 'force quotes')
            ),
           ...reports);
}

function getUpDownPercent({lots, quotes, oldquotes}) {
  const result = {nshares: {}, up_amount: 0, down_amount: 0};
  let up_equity = 0;
  let down_equity = 0;
  let total_equity = 0;
  const symbols = collectSymbols(lots);
  for (const s of symbols) {
    const total_shares = lots.reduce(
      (count, lt) => count + (lt.symbol === s ? lt.nshares : 0), 0);
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

function getAdjustedPrice(lt) {
  return lt.share_price + (lt.share_adj || 0);
}

function getGroupInfo(symbol, lots, date, quotes, oldquotes, yearquotes) {
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
  info.yearquote = (yearquotes && yearquotes[symbol]) || 0;
  info.ytd = (info.yearquote && (info.quote / info.yearquote)) || 0;
  // console.log('ytd', symbol, info.ytd, yearquotes && yearquotes[symbol]);
  info.time_value = info.quote;
  if (opt) {
    const base_quote = quotes[opt[0]] || 0;
    const diff = (base_quote - opt[3]) * (opt[2] === 'P' ? -1 : 1);
    info.in_the_money = (diff > 0);
    if (info.in_the_money)
      info.time_value -= diff;
  }
  const poly = new Polynomial();
  info.total_shares = lots.reduce((total, lt) => total + lt.nshares, 0);
  // For short positions, the gain is computed for negative values.
  // There shouldn't be any return of capital or dividends for short
  // positions because the security isn't owned.
  const sgn = Math.sign(info.total_shares);
  const last_date = lots[lots.length - 1].purchase_date;
  for (const lt of lots) {
    // Note that dividends and return of capital are not per share but
    // total amounts.
    if (lt.dividends)
      info.total_dividends += lt.dividends.reduce((total, d) => total + d.amount, 0);
    const basis = lt.nshares * getAdjustedPrice(lt) +
          Math.abs(lt.nshares) * (lt.share_expense || 0);
    poly.append([sgn * basis, getDelta(lt.purchase_date, date) + lt.wash_days]);
    let return_of_capital = 0;
    if (lt.return_of_capital) {
      for (const r of lt.return_of_capital) {
        return_of_capital += r.amount;
	poly.append([-sgn * r.amount, getDelta(r.date, date)]);
      }
    }
    info.total_basis += basis - return_of_capital;
    info.avg_purchase_price += lt.nshares * getAdjustedPrice(lt) - return_of_capital;
    info.avg_days_held += lt.nshares * (getDelta(lt.purchase_date, date) + lt.wash_days);
  }
  info.avg_days_held /= info.total_shares;
  info.avg_purchase_price /= info.total_shares;
  info.current_value = info.total_shares * info.quote;
  if (Math.abs(info.current_value) > 0.0001 && date > last_date) {
    poly.append([-sgn * info.current_value, 0]);
    info.yield1 = poly.solve();
    // if (symbol === 'AAPL') {
    //   console.log(symbol, info.yield1, poly.compute(info.yield1), poly.elements.slice());
    // }
    // Do this after computing yield1.
    for (const lt of lots) {
      if (lt.dividends)
        for (const d of lt.dividends)
	  poly.append([-sgn * d.amount, getDelta(d.date, date)]);
    }
    info.yield2 = poly.solve();
    // if (symbol === 'AAPL') {
    //   console.log(symbol, info.yield2,  poly.compute(info.yield2), poly.elements.slice());
    // }
  }
  info.gain = (info.current_value + info.total_dividends) / info.total_basis;
  if (info.total_shares < 0)
    info.gain = 2 - info.gain;
  return info;
}

function getSortValue(symbol, lots, quotes) {
  const quote = quotes[symbol] || 0;
  const total_shares = lots.reduce((total, lt) => total + lt.nshares, 0);
  return total_shares * quote;
}

function getSortDividend(symbol, lots, date, quotes, oldquotes) {
  const {
    yield1, yield2
  } = getGroupInfo(symbol, lots, date, quotes, oldquotes);
  return yield1 === 0 ? 0 : yield2 / yield1;
}

function getSortGain(symbol, lots, date, quotes, oldquotes) {
  const {
    gain
  } = getGroupInfo(symbol, lots, date, quotes, oldquotes);
  return gain;
}

function getSortAnnual(symbol, lots, date, quotes, oldquotes) {
  const {
    yield2, total_shares
  } = getGroupInfo(symbol, lots, date, quotes, oldquotes);
  const factor = Math.pow(yield2, 365);
  return (factor - 1) * Math.sign(total_shares);
}

function getSortYtd(symbol, lots, date, quotes, oldquotes, yearquotes) {
  const {
    ytd, total_shares
  } = getGroupInfo(symbol, lots, date, quotes, oldquotes, yearquotes);
  return ytd === 0 ? 0 : total_shares < 0 ? 1 - ytd : ytd - 1;
}

function getAccountInfo({lots, cash, cash_diff, cash_like, cash_like_diff,
                         equity_diff, new_deposits, quotes, oldquotes}) {
  let equity = 0;
  let put_hold = 0;
  for (const lt of lots) {
    const quote = quotes[lt.symbol] || 0;
    const oldquote = oldquotes[lt.symbol] || 0;
    equity += lt.nshares * quote;
    equity_diff += lt.nshares * (quote - oldquote);
    if (lt.nshares < 0) {
      const opt = getOptionParameters(lt.symbol);
      if (opt && opt[2] === 'P')
        put_hold += -lt.nshares * opt[3];
    }
  }
  return {cash, cash_diff, cash_like, cash_like_diff, equity, equity_diff,
          new_deposits, put_hold};
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
                 accounts: data.accounts, quotes: data.quotes, oldquotes: data.oldquotes,
                 yearquotes: data.yearquotes};
  ReactDOM.render(e(PortfolioReport, props), document.getElementById('report'));
}

async function loadData() {
  const urls = [`/portfolioapi/get-report${window.location.search}`,
                `/portfolioapi/get-accounts${window.location.search}`];
  const [data, accounts] = await Promise.all(urls.map(u => makeJSONRequest({url: u})));
  renderReport([data, accounts]);
}

loadData();
