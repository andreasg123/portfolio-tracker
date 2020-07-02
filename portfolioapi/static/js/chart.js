import {api_url_prefix} from './api-url.js';

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

function renderChart(data) {
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
  const url = `${api_url_prefix}get-history${window.location.search}`;
  const res = await fetch(url);
  const data = await res.json();
  renderChart(data);
}

loadData();
