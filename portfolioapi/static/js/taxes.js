import {
  addDays, collectSymbols, formatAmount, formatCount, getLotTotal,
  getOptionParameters, isLong, makeCompletedLots
} from './utils.js';
import {ServerError, StockSymbol} from './ui.js';
import {api_url_prefix} from './api-url.js';

const e = React.createElement;

function TaxTocEntry(props) {
  const suffix = '\u00a0 ';     // '&nbsp; '
  if (props.selected)
    return e(React.Fragment, {}, e('b', {}, props.name), suffix);
  const url = `?account=${props.account}&year=${props.year}`;
  return e(React.Fragment, {}, e('a', {href: url}, props.name), suffix);
}

function TaxToc(props) {
  const y = new Date().getFullYear();
  const account_entries = props.accounts.map(a => e(TaxTocEntry, {
    name: a,
    account: a,
    year: props.year,
    selected: a === props.account}));
  const year_entries = [-2, -1, 0].map(i => e(TaxTocEntry, {
    name: y + i,
    account: props.account,
    year: y + i,
    selected: y + i === props.year}));
  const option_url = `options.html?account=${props.account}`;
  return e(React.Fragment, {},
           ...account_entries, ...year_entries,
           '\u2014 \u00a0',     // '&mdash; &nbsp;'
           e('a', {href: option_url}, 'options'));
}

function TaxHeader(props) {
  const children = [];
  if (props.include_checkbox) {
    const cb_props = {
      type: 'checkbox',
      name: 'all',
      checked: props.checked,
      onChange: props.onChange
    };
    children.push(e('th', {}, e('input', cb_props)));
  }
  children.push(e('th', {className: 'left'}, 'symbol'));
  children.push(e('th', {}, '#'));
  if (props.ndates > 0)
    children.push(e('th', props.ndates > 1 ? {colSpan: props.ndates} : {}, 'date'))
  const columns = ['paid', props.pending ? 'last' : 'close', 'basis', 'amount', 'gain'];
  if (props.has_wash_sale)
    columns.push('wash');
  columns.push('total');
  children.push(...columns.map(c => e('th', {}, c)));
  return e('thead', {}, e('tr', {}, ...children));
}

function DurationHeader(props) {
  return e('tr', {},
           e('td', {className: 'left', colSpan: props.colspan},
             e('b', {}, props.title)));
}

function TaxGroup(props) {
  // console.log(props);
  const info_url = 'http://finance.yahoo.com/quotes/';
  const rows = [];
  for (let i = 0; i < props.lots.length; i++) {
    const lt = props.lots[i];
    const children = [];
    if (props.include_checkbox) {
      const cb_props = {
        type: 'checkbox',
        name: lt.name,
        checked: lt.checked,
        onChange: props.onChange
      };
      children.push(e('td', {}, e('input', cb_props)));
    }
    children.push(e('td', {className: 'left'},
                    e(StockSymbol, {symbol: lt.symbol, url: info_url + lt.symbol})));
    children.push(e('td', {}, formatCount(lt.nshares)));
    children.push(...props.date_props.map(p => e('td', {className: 'small'}, lt[p])));
    children.push(...props.amount_props.map(p => e('td', {className: 'small'},
                                                   formatAmount(lt[p] || 0))));
    children.push(e('td', {}, formatAmount(lt.gain)));
    if (props.has_wash_sale)
      children.push(e('td', {}, lt.wash_sale ? formatAmount(lt.wash_sale * lt.nshares) : ''));
    children.push(e('td', {}, i === props.lots.length - 1 ?
                    formatAmount(props.total_gain) : ''));
    if (props.show_account) {
      const url = `?account=${props.account}&year=${props.year}`;
      children.push(e('td', {className: 'left small', style: {paddingLeft: '1em'}},
                      e('a', {href: url}, lt.account)));
    }
    rows.push(e('tr', {}, ...children));
  }
  return e(React.Fragment, {}, ...rows);
}

function RealizedTaxes(props) {
  const [checked, setChecked] = React.useState(checkAllLots(props.completed_lots,
                                                            props.check_all || false));
  const symbols = collectSymbols(props.completed_lots);
  const cols = (8 + props.date_props.length + (props.include_checkbox ? 1 : 0) +
                (props.has_wash_sale ? 1 : 0));
  const onChange = handleChecked(props.completed_lots, checked, setChecked);
  const th_props = {
    checked: checked.all,
    ndates: props.date_props.length,
    pending: props.pending,
    include_checkbox: props.include_checkbox,
    has_wash_sale: props.has_wash_sale,
    onChange
  };
  const rows = [];
  let nsections = 0;
  let grand_total = 0;
  for (const duration of ['short', 'long']) {
    const rows2 = renderRows({duration, symbols, checked, onChange, ...props});
    if (rows2.length) {
      nsections++;
      const total = computeLotTotal(props.completed_lots, checked, duration === 'long');
      grand_total += total;
      rows.push(e(DurationHeader,
                  {title: duration === 'short' ? 'Short-term' : 'Long-term',
                   colspan: cols}),
                ...rows2,
                e('tr', {},
                  e('td', {colSpan: cols - 1}),
                  e('td', {},
                    e('b', {}, formatAmount(total)))));
    }
  }
  if (nsections == 2) {
    rows.push(e('tr', {},
                e('td', {className: 'left', style: {borderTop: '1px solid black'},
                         colSpan: cols - 1},
                  e('b', {}, 'Grand total')),
                e('td', {style: {borderTop: '1px solid black'}},
                  e('b', {}, formatAmount(grand_total)))));
  }
  if (!rows.length)
    return e(React.Fragment);
  return e('table', {cellSpacing: 0},
           e(TaxHeader, th_props),
           e('tbody', {}, ...rows));
}

function handleChecked(completed_lots, checked, setChecked) {
  return evt => {
    const target = evt.target;
    const value = target.checked
    const name = target.name;
    if (name === 'all')
      setChecked(checkAllLots(completed_lots, value));
    else {
      const updated = {
        [name]: value
      };
      const idx = Number(name);
      const symbol = completed_lots[idx].symbol;
      const account = completed_lots[idx].account;
      // Find the newest checked or oldest unchecked.
      const newest = completed_lots.reduce(
        (newest, lt, i) => lt.symbol === symbol && lt.account === account &&
          (i === idx || checked[i] === value) &&
          (!newest || (lt.start_date > newest) === value) ? lt.start_date : newest,
        null);
      completed_lots.forEach((lt, i) => {
        if (i !== idx && lt.symbol === symbol && lt.account === account &&
            (lt.start_date === newest || (lt.start_date < newest) === value))
          updated[i] = value;
      });
      setChecked({...checked, ...updated});
    }
  };
}

function renderRows({completed_lots, date_props, include_checkbox,
                     has_wash_sale, duration, symbols, show_account, year,
                     onChange, checked}) {
  const amount_props = ['start_share_price', 'end_share_price', 'basis', 'amount'];
  const rows = [];
  for (const s of symbols) {
    const lots = [];
    let total_gain = 0;
    for (let i = completed_lots.length - 1; i >= 0; i--) {
      const lt = completed_lots[i];
      let sym = lt.symbol;
      const opt = getOptionParameters(sym);
      if (opt)
        sym = opt[0];
      if (sym !== s)
        continue;
      if (isLong(lt) !== (duration === 'long'))
        continue;
      const total = getLotTotal(lt);
      total_gain += total.gain;
      lots.push({
        ...lt, ...total,
        name: i,
        checked: checked[i]
      });
    }
    if (lots.length) {
      rows.push(e(TaxGroup, {
        lots, total_gain,
        date_props, amount_props,
        include_checkbox, has_wash_sale,
        show_account, year,
        onChange
      }));
    }
  }
  return rows;
}

function checkAllLots(completed_lots, on) {
  const checked = completed_lots.reduce((checked, lt, i) => {
    checked[i] = on;
    return checked;
  }, {});
  checked.all = on;
  return checked;
}

function computeLotTotal(completed_lots, checked, is_long) {
  return completed_lots.reduce(
    (total, lt, i) => total + (checked[i] && isLong(lt) === is_long ?
                               getLotTotal(lt).gain : 0),
    0);
}

function DividendRow(props) {
  return e('tr', {},
           e('td', {className: 'left'}, props.symbol),
           e('td', {}, formatAmount(props.dividend)));
}

function Dividend(props) {
  const keys = Object.keys(props.dividend || {});
  if (!keys.length)
    return e(React.Fragment);
  keys.sort();
  const total = keys.reduce((total, k) => total + props.dividend[k], 0);
  const rows = keys.map(k => e(DividendRow, {symbol: k, dividend: props.dividend[k]}));
  rows.push(e('tr', {}, e('td'), e('td', {}, e('b', {}, formatAmount(total)))));
  return e('table', {cellSpacing: 0},
           e('thead', {}, e('tr', {}, e('th', {}, 'symbol'), e('th', {}, 'dividend'))),
           e('tbody', {}, ...rows));
}

function WashSaleRow(props) {
  return e('tr', {},
           e('td', {className: 'left'}, props.symbol),
           e('td', {}, props.date));
}

function WashSales(props) {
  const losses = new Map();
  for (const lt of props.completed_lots) {
    if (lt.nshares < 0 || getOptionParameters(lt.symbol))
      continue;
    const start_share_price = lt.start_share_price || 0;
    const end_share_price = lt.end_share_price || 0;
    const start_share_expense = lt.start_share_expense || 0;
    const end_share_expense = lt.end_share_expense || 0;
    const start_share_adj = lt.start_share_adj || 0;
    const end_share_adj = lt.end_share_adj || 0;
    const amount = (lt.nshares * end_share_price -
                    Math.abs(lt.nshares) * (end_share_adj + end_share_expense));
    const basis = (lt.nshares * start_share_price +
                   Math.abs(lt.nshares) * (start_share_adj + start_share_expense));
    if (amount < basis) {
      const prev = losses.get(lt.symbol);
      if (!prev || prev < lt.end_date)
        losses.set(lt.symbol, lt.end_date);
    }
  }
  const sorted = Array.from(losses.entries());
  if (!sorted.length)
    return e(React.Fragment);
  const rows = sorted.map(s => e(WashSaleRow, {symbol: s[0], date: addDays(s[1], 31)}));
  return e(React.Fragment, {},
           e('h4', {style: {marginBottom: 0}}, 'End of Wash Sale Restrictions'),
           e('table', {cellSpacing: 0},
             e('tbody', {}, ...rows)),
           e('p', {},
             e('b', {}, 'Note:'),
             ' ',
             e('a', {href: 'https://en.wikipedia.org/wiki/Wash_sale'}, 'Wash sales'),
             ' are across accounts, including buying stocks in IRA accounts within 30 days. Here, only the restrictions caused by this account are shown. Also, at the start of the year, one should check the previous year, too.'));
}

function renderError(data) {
  ReactDOM.render(e(ServerError, {error: data.error}),
                  document.getElementById('taxes'));
}

function renderToc(account, year, accounts) {
  const container = document.getElementById('toc');
  ReactDOM.render(e(TaxToc, {account, year, accounts}), container);
}

const show_dates = true;
const show_final_checkboxes = true;

function renderPending(data) {
  // end_date isn't rendered but it's needed to determine long-term positions.
  if (!data.lots.length)
    return;
  const end_date = `${data.year}-12-31`;
  const date_props = show_dates ? ['start_date'] : [];
  const props = {
    completed_lots: makeCompletedLots(data.lots, data.quotes, end_date),
    date_props,
    pending: true,
    include_checkbox: true,
    check_all: false,
    has_wash_sale: false,
    show_account: data.account === 'combined' || data.account === 'taxable',
    year: data.year
  };
  ReactDOM.render(e(React.Fragment, {},
                    e('h3', {}, 'Open'),
                    e(RealizedTaxes, props)),
                  document.getElementById('pending'));
}

function renderDividend(data) {
  if (!Object.keys(data.dividend).length)
    return;
  ReactDOM.render(e(React.Fragment, {},
                    e('h3', {}, 'Dividends'),
                    e(Dividend, {dividend: data.dividend})),
                  document.getElementById('dividend'));
}

function renderWashSales(data) {
  const props = {
    completed_lots: data.completed_lots
  };
  ReactDOM.render(e(WashSales, props), document.getElementById('wash-sales'));
}

function renderTaxes([data, accounts]) {
  // console.log('renderTaxes', data, accounts);
  if (data.error) {
    renderError(data);
    return;
  }
  renderToc(data.account, Number(data.year), [...accounts.accounts, 'combined', 'taxable']);
  data.lots.forEach(lt => {
    if (lt.wash_days) {
      lt.purchase_date = addDays(lt.purchase_date, -lt.wash_days);
    }
  });
  data.completed_lots.forEach(clt => {
    if (clt.wash_days) {
      clt.start_date = addDays(clt.start_date, -clt.wash_days);
    }
  });
  const date_props = show_dates ? ['start_date', 'end_date'] : ['end_date'];
  for (const clt of data.completed_lots) {
    if (clt.wash_sale !== 0) {
      console.log(clt);
    }
  }
  const props = {
    completed_lots: data.completed_lots,
    date_props,
    include_checkbox: show_final_checkboxes,
    check_all: true,
    has_wash_sale: data.completed_lots.some(clt => clt.wash_sale !== 0),
    show_account: data.account === 'combined' || data.account === 'taxable',
    year: data.year
  };
  ReactDOM.render(e(RealizedTaxes, props), document.getElementById('taxes'));
  renderPending(data);
  renderDividend(data);
  renderWashSales(data);
}

async function loadData() {
  const urls = [`${api_url_prefix}get-taxes${window.location.search}`,
                `${api_url_prefix}get-accounts${window.location.search}`];
  const params = new URLSearchParams(window.location.search.substring(1));
  if (!params.get('year')) {
    const year = new Date().getFullYear();
    for (let i = 0; i < urls.length; i++) {
      urls[i] += `${window.location.search ? '&' : '?'}year=${year}`;
    }
  }
  const [data, accounts] = await Promise.all(urls.map(u => fetch(u).then(res => res.json())));
  renderTaxes([data, accounts]);
}

loadData();
