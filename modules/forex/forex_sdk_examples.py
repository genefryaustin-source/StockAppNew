"""
modules/forex/forex_sdk_examples.py

Example usage for the Forex SDK.
"""

from modules.forex.forex_sdk import get_forex_sdk

def example_initialize(db=None):
    sdk=get_forex_sdk(db=db)
    return sdk.initialize()

def example_health(db=None):
    return get_forex_sdk(db=db).health()

def example_quote(pair="EURUSD", db=None):
    return get_forex_sdk(db=db).quotes(pair)

def example_submit_order(db=None):
    sdk=get_forex_sdk(db=db)
    return sdk.submit_order(
        pair="EURUSD",
        side="BUY",
        units=10000,
        order_type="MARKET",
    )

def example_portfolio(db=None):
    return get_forex_sdk(db=db).portfolio_summary()

def example_validation(db=None):
    return get_forex_sdk(db=db).validate()

def run_examples(db=None):
    return {
        "health": example_health(db),
        "quote": example_quote(db=db),
        "portfolio": example_portfolio(db),
    }
