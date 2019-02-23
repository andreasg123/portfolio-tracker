export function makeJSONRequest({method, url, data, headers, timeout, response_type}) {
  return new Promise((resolve, reject) => {
    const req = new XMLHttpRequest();
    if (timeout)
      req.timeout = timeout;
    const handle_event = (req, evt) => {
      return () => {
        if (evt === 'load') {
          resolve(req.response);
        }
        else
          reject(req.response);
      };
    };
    const events = ['load', 'error', 'abort', 'timeout'];
    for (let i = 0; i < events.length; i++)
      req['on' + events[i]] = handle_event(req, events[i]);
    req.open(method, url, true);
    for (let h in headers)
      req.setRequestHeader(h, headers[h]);
    req.responseType = response_type || 'json';
    req.send(data);
  });
}
