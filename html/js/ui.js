import {getOptionParameters, toUSDate} from './utils.js';

const e = React.createElement;

export function ServerError(props) {
  const lines = Array.isArray(props.error) ? props.error : [props.error];
  return e('pre', {}, ...lines);
}

export function StockSymbol(props) {
  const opt = getOptionParameters(props.symbol);
  const anchor = !opt ? props.symbol :
        e(React.Fragment, {},
          opt[0],
          e('span', {className: 'small'},
            ` ${toUSDate(opt[1])} ${opt[3].toFixed(2)} ${opt[2]}`));
  return props.url ? e('a', {href: props.url}, anchor) : anchor;
}
