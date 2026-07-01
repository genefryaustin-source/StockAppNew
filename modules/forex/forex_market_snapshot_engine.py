"""
modules/forex/forex_market_snapshot_engine.py

Phase 16A — Market snapshot engine.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


DEFAULT_PAIRS = ["EUR/USD","USD/JPY","GBP/USD","USD/CHF","AUD/USD","USD/CAD","NZD/USD","EUR/JPY","EUR/GBP","GBP/JPY"]


class ForexMarketSnapshotEngine:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def snapshot(self, pairs: Optional[List[str]] = None) -> Dict[str, Any]:
        from modules.forex.forex_quote_aggregator import get_forex_quote_aggregator
        from modules.forex.forex_tick_cache import get_forex_tick_cache
        from modules.forex.forex_data_quality_monitor import get_forex_data_quality_monitor

        agg = get_forex_quote_aggregator(db=self.db)
        cache = get_forex_tick_cache(db=self.db)
        quotes = []
        for pair in pairs or DEFAULT_PAIRS:
            q = agg.quote(pair)
            cache.add_tick(pair, q)
            quotes.append(q)
        quality = get_forex_data_quality_monitor(db=self.db).dashboard(quotes)
        return {
            "status": "READY",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "quotes": quotes,
            "quality": quality,
            "cache": cache.summary(),
        }


_ENGINE = None


def get_forex_market_snapshot_engine(db: Optional[Any] = None) -> ForexMarketSnapshotEngine:
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None):
        _ENGINE = ForexMarketSnapshotEngine(db=db)
    return _ENGINE
