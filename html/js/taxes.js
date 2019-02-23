import {makeJSONRequest} from './xhr.js';
import {
  addDays, collectSymbols, formatAmount, formatCount, getBucketTotal,
  getOptionParameters, isLong, makeCompletedBuckets
} from './utils.js';
import {ServerError, StockSymbol} from './ui.js';

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
  children.push(...columns.map(c => e('th', {}, c)));
  return e('thead', {}, e('tr', {}, ...children));
}

function DurationHeader(props) {
  return e('tr', {},
           e('td', {className: 'left', colSpan: props.colspan},
             e('b', {}, props.title)));
}

function TaxRow(props) {
  // console.log(props);
  const info_url = 'http://finance.yahoo.com/quotes/';
  const children = [];
  if (props.include_checkbox) {
    const cb_props = {
      type: 'checkbox',
      name: props.name,
      checked: props.checked,
      onChange: props.onChange
    };
    children.push(e('td', {}, e('input', cb_props)));
  }
  children.push(e('td', {className: 'left'},
                  e(StockSymbol, {symbol: props.symbol, url: info_url + props.symbol})));
  children.push(e('td', {}, formatCount(props.nshares)));
  children.push(...props.date_props.map(p => e('td', {className: 'small'},
                                               props[p])));
  children.push(...props.amount_props.map(p => e('td', {className: 'small'},
                                                 formatAmount(props[p] || 0))));
  children.push(e('td', {}, formatAmount(props.gain)));
  if (props.has_wash_sale)
    children.push(e('td', {}, props.wash_sale ? formatAmount(props.wash_sale) : ''));
  if (props.show_account) {
    const url = `?account=${props.account}&year=${props.year}`;
    children.push(e('td', {className: 'left small', style: {paddingLeft: '1em'}},
                    e('a', {href: url}, props.account)));
  }
  return e('tr', {}, ...children);
}

class RealizedTaxes extends React.Component {
  constructor(props) {
    super(props);
    this.handleCheckboxChange = this.handleCheckboxChange.bind(this);
    this.state = RealizedTaxes.getBucketState(props.completed_buckets,
                                              props.check_all || false)
  }

  static getBucketState(completed_buckets, checked) {
    const state = completed_buckets.reduce((state, cb, i) => {
      state[i] = checked;
      return state;
    }, {});
    state.all = checked;
    return state;
  }

  handleCheckboxChange(evt) {
    const target = evt.target;
    const value = target.checked
    const name = target.name;
    // console.log('handleCheckboxChange', name, value);
    if (name === 'all')
      this.setState(RealizedTaxes.getBucketState(this.props.completed_buckets, value));
    else {
      const state = {
        [name]: value
      };
      const idx = Number(name);
      const symbol = this.props.completed_buckets[idx].symbol;
      // Find the newest checked or oldest unchecked.
      const newest = this.props.completed_buckets.reduce(
        (newest, b, i) => b.symbol === symbol &&
          (i === idx || this.state[i] === value) &&
          (!newest || (b.start_date > newest) === value) ? b.start_date : newest,
        null);
      this.props.completed_buckets.forEach((b, i) => {
        if (i !== idx && b.symbol === symbol &&
            (b.start_date === newest || (b.start_date < newest) === value))
          state[i] = value;
      });
      this.setState(state);
    }
  }

  computeTotal(is_long) {
    return this.props.completed_buckets.reduce(
      (total, b, i) => total + (this.state[i] && isLong(b) === is_long ?
                                getBucketTotal(b).gain : 0),
      0);
  }

  renderRows(duration, symbols, show_account, year) {
    const rows = [];
    for (const s of symbols) {
      for (let i = this.props.completed_buckets.length - 1; i >= 0; i--) {
        const b = this.props.completed_buckets[i];
        let sym = b.symbol;
        const opt = getOptionParameters(sym);
        if (opt)
          sym = opt[0];
        if (sym !== s)
          continue;
        if (isLong(b) !== (duration === 'long'))
          continue;
        const total = getBucketTotal(b);
        const amount_props = ['start_share_price', 'end_share_price', 'basis', 'amount'];
        const date_props = this.props.date_props;
        const row_props = {
          ...b, ...total, date_props, amount_props,
          name: i,
          include_checkbox: this.props.include_checkbox,
          has_wash_sale: this.props.has_wash_sale,
          show_account, year,
          checked: this.state[i],
          onChange: this.handleCheckboxChange
        };
        rows.push(e(TaxRow, row_props));
      }
    }
    return rows;
  }

  render() {
    const symbols = collectSymbols(this.props.completed_buckets);
    const cols = (7 + this.props.date_props.length +
                  (this.props.include_checkbox ? 1 : 0));
    const th_props = {
      checked: this.state.all,
      ndates: this.props.date_props.length,
      pending: this.props.pending,
      include_checkbox: this.props.include_checkbox,
      has_wash_sale: this.props.has_wash_sale,
      onChange: this.handleCheckboxChange
    };
    const rows = [];
    const short_rows = this.renderRows('short', symbols, this.props.show_account, this.props.year);
    if (short_rows.length) {
      rows.push(e(DurationHeader, {title: 'Short-term', colspan: cols}),
                ...short_rows,
                e('tr', {},
                  e('td', {colSpan: cols - 1}),
                  e('td', {},
                    e('b', {}, formatAmount(this.computeTotal(false))))));
    }
    const long_rows = this.renderRows('long', symbols, this.props.show_account, this.props.year);
    if (long_rows.length) {
      rows.push(e(DurationHeader, {title: 'Long-term', colspan: cols}),
                ...long_rows,
                e('tr', {},
                  e('td', {colSpan: cols - 1}),
                  e('td', {},
                    e('b', {}, formatAmount(this.computeTotal(true))))));
    }
    if (!rows.length)
      return e(React.Fragment);
    return e('table', {cellSpacing: 0},
             e(TaxHeader, th_props),
             e('tbody', {}, ...rows));
  }
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
  for (const b of props.completed_buckets) {
    if (b.nshares < 0 || getOptionParameters(b.symbol))
      continue;
    const start_share_price = b.start_share_price || 0;
    const end_share_price = b.end_share_price || 0;
    const start_share_expense = b.start_share_expense || 0;
    const end_share_expense = b.end_share_expense || 0;
    const start_share_adj = b.start_share_adj || 0;
    const end_share_adj = b.end_share_adj || 0;
    const amount = (b.nshares * end_share_price -
                    Math.abs(b.nshares) * (end_share_adj + end_share_expense));
    const basis = (b.nshares * start_share_price +
                   Math.abs(b.nshares) * (start_share_adj + start_share_expense));
    if (amount < basis) {
      const prev = losses.get(b.symbol);
      if (!prev || prev < b.end_date)
        losses.set(b.symbol, b.end_date);
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

function renderTaxes([data, accounts]) {
  // console.log('renderTaxes', data, accounts);
  if (data.error) {
    renderError(data);
    return;
  }
  renderToc(data.account, Number(data.year), [...accounts.accounts, 'combined']);
  const date_props = show_dates ? ['start_date', 'end_date'] : ['end_date'];
  const props = {
    completed_buckets: data.completed_buckets,
    date_props,
    include_checkbox: show_final_checkboxes,
    check_all: true,
    has_wash_sale: data.completed_buckets.some(cb => cb.wash_sale !== 0),
    show_account: data.account === 'combined',
    year: data.year
  };
  ReactDOM.render(e(RealizedTaxes, props), document.getElementById('taxes'));
  renderPending(data);
  renderDividend(data);
  renderWashSales(data);
}

function renderPending(data) {
  // end_date isn't rendered but it's needed to determine long-term positions.
  if (!data.buckets.length)
    return;
  const end_date = `${data.year}-12-31`;
  const date_props = show_dates ? ['start_date'] : [];
  const props = {
    completed_buckets: makeCompletedBuckets(data.buckets, data.quotes, end_date),
    date_props,
    pending: true,
    include_checkbox: true,
    check_all: false,
    has_wash_sale: false,
    show_account: data.account === 'combined',
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
    completed_buckets: data.completed_buckets
  };
  ReactDOM.render(e(WashSales, props), document.getElementById('wash-sales'));
}

let url = `/portfolioapi/get-taxes${window.location.search}`;
const params = new URLSearchParams(window.location.search.substring(1));
if (!params.get('year')) {
  const year = new Date().getFullYear();
  url += `${window.location.search ? '&' : '?'}year=${year}`;
}
Promise.all([url, '/portfolioapi/get-accounts'].map(u => makeJSONRequest({method: 'GET', url: u})))
  .then(renderTaxes);
