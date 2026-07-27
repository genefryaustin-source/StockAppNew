"""
modules/forex/forex_market_depth.py

FX market depth and DOM summary.

Liquidity/imbalance/depth-score metrics genuinely require an L2 order-book
feed (bid/ask size at multiple levels), which forex_order_book.py no longer
fabricates -- it now returns only the real top-of-book quote with no size
data. So this module honestly reports those metrics as unavailable instead
of summing placeholder sizes into a fake liquidity/imbalance number. Only
the real spread (and status/pair) are populated from live data.
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
        status = book.get("status", "NO_DATA")

        return {
            "status": status,
            "pair": book.get("pair", pair),
            "bid_liquidity_m": None,
            "ask_liquidity_m": None,
            "liquidity_imbalance_pct": None,
            "dominant_side": "UNKNOWN",
            "spread": book.get("spread"),
            "depth_score": None,
            "error": book.get("error"),
            "note": (
                "Liquidity/imbalance/depth-score require an L2 order-book feed, "
                "which isn't connected -- only the live top-of-book spread above "
                "is real. See forex_order_book.py."
            ),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


_DEPTH = None


def get_forex_market_depth(db: Optional[Any] = None) -> ForexMarketDepth:
    global _DEPTH
    if _DEPTH is None or (db is not None and _DEPTH.db is None):
        _DEPTH = ForexMarketDepth(db=db)
    return _DEPTH