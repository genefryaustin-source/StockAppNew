"""
modules/forex/forex_market_data_fabric.py

Phase 16A — Multi-source market data fabric.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


class ForexMarketDataFabric:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def fabric_snapshot(self, **kwargs) -> Dict[str, Any]:
        from modules.forex.forex_market_snapshot_engine import get_forex_market_snapshot_engine
        snapshot = get_forex_market_snapshot_engine(db=self.db).snapshot(pairs=kwargs.get("pairs"))
        return {
            "status": "READY",
            "component": "forex_market_data_fabric",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "market_snapshot": snapshot,
            "provider_failover": {
                "enabled": True,
                "order": ["Polygon", "Finnhub", "AlphaVantage", "TwelveData", "Yahoo"],
            },
        }


_FABRIC = None


def get_forex_market_data_fabric(db: Optional[Any] = None) -> ForexMarketDataFabric:
    global _FABRIC
    if _FABRIC is None or (db is not None and _FABRIC.db is None):
        _FABRIC = ForexMarketDataFabric(db=db)
    return _FABRIC
