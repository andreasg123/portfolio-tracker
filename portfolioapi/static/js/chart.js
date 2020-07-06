import {api_url_prefix} from './api-url.js';

const e = React.createElement;

function ChartTocEntry(props) {
  const suffix = '\u00a0 ';     // '&nbsp; '
  if (props.selected)
    return e(React.Fragment, {}, e('b', {}, props.account), suffix);
  let url = `?account=${props.account}`;
  if (props.start) {
    url += `&start=${props.start}`;
  }
  if (props.end) {
    url += `&end=${props.end}`;
  }
  return e(React.Fragment, {}, e('a', {href: url}, props.account), suffix);
}

function ChartToc(props) {
  console.log('ChartToc', props);
  const account_entries = props.accounts.map(a => e(ChartTocEntry, {
    account: a,
    start: props.start,
    end: props.end,
    selected: a === props.account}));
  return e(React.Fragment, {}, ...account_entries);
}

function toDate(d) {
  const values = d.split(/\D/).map(Number);
  values[1]--;
  return new Date(...values);
}

function addAxes(svg, xScale, yScale, width, height) {
  // Axes
  const xAxis = d3.axisBottom(xScale);
  const yAxis = d3.axisLeft(yScale);
  svg.append('g')
    .attr('class', 'x axis')
    .attr('transform', `translate(0,${height})`)
    .call(d3.axisBottom(xScale).tickFormat(d3.timeFormat('%Y-%m-%d')));
  svg.append('g')
    .attr('class', 'y axis')
    .call(d3.axisLeft(yScale));
  // Grid
  svg.append('g')			
    .attr('class', 'grid')
    .attr('transform', `translate(0,${height})`)
    .call(xAxis
          .tickSize(-height)
          .tickFormat(''));
  svg.append('g')			
    .attr('class', 'grid')
    .call(yAxis
          .tickSize(-width)
          .tickFormat(''));
}

function addData(svg, data, color) {
  const lines = svg.append('g')
        .attr('class', 'line')
        .selectAll('path')
        .data(data)
        .enter().append('path')
        .style('stroke', (_, i) => color(i))
        .attr('d', d3.line());
}

function renderToc(accounts, account, start, end) {
  const container = document.getElementById('toc');
  ReactDOM.render(e(ChartToc, {account, accounts, start, end}), container);
}

function renderChart([data, accounts, account, start, end]) {
  renderToc(accounts.accounts, account, start, end);
  const min_y = data.reduce((min_y, d) => Math.min(
    min_y, Math.min(d.deposits, d.equity + d.cash)), Number.MAX_VALUE);
  const max_y = data.reduce((max_y, d) => Math.max(
    max_y, Math.max(d.deposits, d.equity + d.cash)), 0);
  const min_x = toDate(data[0].date);
  const max_x = toDate(data[data.length - 1].date);
  const margin = {top: 5, right: 15, bottom: 20, left: 60};
  const width = 1000;
  const height = 600;
  const svg = d3.select('#chart')
        .append('svg')
        .attr('width', width + margin.left + margin.right)
        .attr('height', height + margin.top + margin.bottom)
        .append('g')
        .attr('transform', `translate(${margin.left},${margin.top})`);
  const xScale = d3.scaleTime()
        .domain([min_x, max_x])
        .range([0, width]);
  const yScale = d3.scaleLinear()
        .domain([min_y, max_y])
        .nice()
        .range([height, 0]);
  data = [data.map(d => [xScale(toDate(d.date)), yScale(d.deposits)]),
          data.map(d => [xScale(toDate(d.date)), yScale(d.equity + d.cash)])];
  const color = d3.scaleOrdinal(d3.schemePaired);
  addAxes(svg, xScale, yScale, width, height);
  addData(svg, data, color);
}

async function loadData() {
  const urls = [`${api_url_prefix}get-history${window.location.search}`,
                `${api_url_prefix}get-accounts`];
  const params = new URLSearchParams(window.location.search.substring(1));
  const account = params.get('account');
  const start = params.get('start');
  const end = params.get('end');
  const [data, accounts] = await Promise.all(urls.map(u => fetch(u).then(res => res.json())));
  renderChart([data, accounts, account, start, end]);
}

loadData();
