# -*- coding: utf-8 -*-

from flask import Flask
import os


def create_app(test_config=None):
    app = Flask(__name__)
    if test_config is not None:
        app.config.from_mapping(test_config)
    if app.config['TESTING']:
        from . import portfolio, stockquotes
        tests_data = os.path.realpath(os.path.join(os.path.dirname(__file__),
                                                   '../tests/data'))
        quote_dir = os.path.join(tests_data, 'quotes')
        stockquotes.setQuotePaths(quote_dir,
                                  os.path.join(tests_data, 'cache/quotes.db'))
        portfolio.setDataPaths(tests_data, os.path.join(tests_data, 'cache'))
    from . import views
    app.register_blueprint(views.bp)
    return app
