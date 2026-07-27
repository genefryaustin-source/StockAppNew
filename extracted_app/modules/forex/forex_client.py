"""
modules/forex/forex_client.py

High-level client wrapper for applications consuming the Forex API.
"""

from __future__ import annotations
from typing import Any

from modules.forex.forex_api import get_forex_api


class ForexClient:
    def __init__(self, db=None):
        self.db=db
        self.api=get_forex_api(db=db)

    def call(self, action:str, **kwargs)->Any:
        return self.api.execute(action, **kwargs)

    def initialize(self):
        return self.call("initialize")

    def health(self):
        return self.call("health")

    def status(self):
        return self.call("status")

    def quote(self, pair:str):
        return self.call("quotes", pairs=pair)

    def submit_order(self, **kwargs):
        return self.call("submit_order", **kwargs)

    def portfolio(self, **kwargs):
        return self.call("portfolio_summary", **kwargs)

    def validate(self):
        return self.call("validate")

    def enterprise_snapshot(self):
        return self.call("enterprise_snapshot")

_CLIENT=None

def get_forex_client(db=None)->ForexClient:
    global _CLIENT
    if _CLIENT is None or (db is not None and _CLIENT.db is None):
        _CLIENT=ForexClient(db=db)
    return _CLIENT
