"""
modules/forex/forex_api.py

Unified API facade exposing the Forex SDK to the rest of StockApp.
"""

from __future__ import annotations
from typing import Any, Dict

from modules.forex.forex_sdk import get_forex_sdk


class ForexAPI:
    def __init__(self, db=None):
        self.db=db
        self.sdk=get_forex_sdk(db=db)

    def execute(self, action:str, **kwargs)->Any:
        if not hasattr(self.sdk, action):
            return {"status":"ERROR","message":f"Unknown action: {action}"}
        return getattr(self.sdk, action)(**kwargs)

    def info(self)->Dict[str,Any]:
        return {
            "name":"ForexAPI",
            "version":"1.0.0",
            "sdk":"ForexSDK",
            "status":"READY",
        }

_API=None

def get_forex_api(db=None)->ForexAPI:
    global _API
    if _API is None or (db is not None and _API.db is None):
        _API=ForexAPI(db=db)
    return _API
