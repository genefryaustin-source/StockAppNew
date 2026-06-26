"""
modules/forex/forex_market_depth.py

FX market depth and DOM summary.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


class ForexMarketDepth:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def depth(self, pair: str = "EUR/USD", **kwargs) -> Dict[str, Any]:
        from modules.forex.forex_order_book import get_forex_order_book

        book = get_forex_order_book(db=self.db).book(pair=pair)
        bid_liquidity = sum(row.get("size_m", 0) for row in book.get("bids", []))
        ask_liquidity = sum(row.get("size_m", 0) for row in book.get("asks", []))
        imbalance = (bid_liquidity - ask_liquidity) / max(bid_liquidity + ask_liquidity, 1) * 100.0

        return {
            "status": "READY",
            "pair": book.get("pair"),
            "bid_liquidity_m": round(bid_liquidity, 2),
            "ask_liquidity_m": round(ask_liquidity, 2),
            "liquidity_imbalance_pct": round(imbalance, 4),
            "dominant_side": "BID" if imbalance > 5 else "ASK" if imbalance < -5 else "BALANCED",
            "spread": book.get("spread"),
            "depth_score": round(max(0, min(100, 75 + abs(imbalance) / 2)), 2),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


_DEPTH = None


def get_forex_market_depth(db: Optional[Any] = None) -> ForexMarketDepth:
    global _DEPTH
    if _DEPTH is None or (db is not None and _DEPTH.db is None):
        _DEPTH = ForexMarketDepth(db=db)
    return _DEPTH
