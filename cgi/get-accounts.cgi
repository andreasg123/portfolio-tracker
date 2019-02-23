#!/usr/bin/python3

import datetime
import json
import sys
import traceback

from portfolio import Portfolio, Transaction

sys.stdout.write('Content-type: application/json\n')
sys.stdout.write('\n')
sys.stdout.flush()

try:
    files = Transaction.getAccounts()
    data = {'accounts': files}
except:
    type, value, tb = sys.exc_info()
    data = {'error': traceback.format_exception(type, value, tb)}

json_data = json.dumps(data, separators=(',', ':'))
sys.stdout.write(json_data)
