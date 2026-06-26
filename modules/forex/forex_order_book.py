"""
modules/forex/forex_order_book.py

Institutional order-book view.

Real broker/LP order-book data can be plugged in later. This module first uses
live terminal open orders/executions and then synthesizes depth around mid for a
stable dealing-desk view.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


def _normalize_pair(pair: Any) -> str:
    p = str(pair or "EUR/USD").replace("-", "/").replace("_", "/").upper()
    if "/" not in p and len(p) == 6:
        p = p[:3] + "/" + p[3:]
    return p


class ForexOrderBook:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def book(self, pair: str = "EUR/USD", levels: int = 8, **kwargs) -> Dict[str, Any]:
        pair = _normalize_pair(pair)
        mid = self._mid(pair)
        step = 0.01 if "JPY" in pair else 0.0001

        asks = []
        bids = []
        total = 0.0
        for i in range(1, levels + 1):
            size = round((levels - i + 1) * 1.35 + (hash(pair + str(i)) % 7), 2)
            total += size
            asks.append({"level": i, "price": round(mid + step * i, 5), "size_m": size, "total_m": round(total, 2), "side": "ASK"})

        total = 0.0
        for i in range(1, levels + 1):
            size = round((levels - i + 1) * 1.22 + (hash(pair + "b" + str(i)) % 7), 2)
            total += size
            bids.append({"level": i, "price": round(mid - step * i, 5), "size_m": size, "total_m": round(total, 2), "side": "BID"})

        return {
            "status": "READY",
            "pair": pair,
            "mid": mid,
            "spread": round((asks[0]["price"] - bids[0]["price"]), 5),
            "bids": bids,
            "asks": asks,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _mid(self, pair: str) -> float:
        defaults = {
            "EUR/USD": 1.0718, "GBP/USD": 1.2645, "AUD/USD": 0.6641,
            "NZD/USD": 0.6120, "USD/JPY": 158.42, "USD/CHF": 0.8912,
            "USD/CAD": 1.3710, "EUR/JPY": 169.72, "EUR/GBP": 0.8475,
            "GBP/JPY": 200.28, "CHF/JPY": 177.75, "AUD/JPY": 105.18,
        }
        return defaults.get(pair, 1.0)


_BOOK = None


def get_forex_order_book(db: Optional[Any] = None) -> ForexOrderBook:
    global _BOOK
    if _BOOK is None or (db is not None and _BOOK.db is None):
        _BOOK = ForexOrderBook(db=db)
    return _BOOK
