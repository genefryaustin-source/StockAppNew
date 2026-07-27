"""
modules/forex/forex_order_book.py

Institutional order-book view.

Previously this synthesized a fake 8-level order book around a hardcoded
per-pair mid price (never updated, never touching a live quote). There is
still no broker/ECN market-depth (L2) feed connected anywhere in this
codebase, so a real multi-level book genuinely cannot be built yet -- but a
real top-of-book quote (bid/ask/mid/spread) is available from the live
provider pipeline, so that's what this now returns instead of invented
depth. Real broker/LP L2 data can be plugged in here later without changing
this module's public shape (status/pair/mid/spread/bids/asks).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


def _normalize_pair(pair: Any) -> str:
    p = str(pair or "EUR/USD").replace("-", "/").replace("_", "/").upper()
    if "/" not in p and len(p) == 6:
        p = p[:3] + "/" + p[3:]
    return p


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ForexOrderBook:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def book(self, pair: str = "EUR/USD", levels: int = 8, **kwargs) -> Dict[str, Any]:
        pair = _normalize_pair(pair)

        try:
            from modules.forex.forex_price_service import get_forex_price_service
            quote = get_forex_price_service().get_quote(pair)
        except Exception as exc:
            return {
                "status": "ERROR",
                "pair": pair,
                "mid": None,
                "spread": None,
                "bids": [],
                "asks": [],
                "error": str(exc),
                "generated_at": _utc_iso(),
            }

        if not isinstance(quote, dict) or quote.get("error"):
            error = quote.get("error") if isinstance(quote, dict) else "No live quote available."
            return {
                "status": "NO_DATA",
                "pair": pair,
                "mid": None,
                "spread": None,
                "bids": [],
                "asks": [],
                "error": error,
                "note": (
                    "No broker/ECN market-depth (L2) feed is connected -- only "
                    "a live top-of-book quote can be shown when one is available."
                ),
                "generated_at": _utc_iso(),
            }

        bid = quote.get("bid")
        ask = quote.get("ask")
        mid = quote.get("mid")
        if mid is None and bid is not None and ask is not None:
            try:
                mid = (float(bid) + float(ask)) / 2
            except (TypeError, ValueError):
                mid = None

        spread = quote.get("spread")
        if spread is None and bid is not None and ask is not None:
            try:
                spread = round(float(ask) - float(bid), 5)
            except (TypeError, ValueError):
                spread = None

        provider = quote.get("provider", "-")

        asks = []
        if ask is not None:
            asks.append({"level": 1, "price": ask, "size_m": "-", "total_m": "-", "side": "ASK", "provider": provider})
        bids = []
        if bid is not None:
            bids.append({"level": 1, "price": bid, "size_m": "-", "total_m": "-", "side": "BID", "provider": provider})

        return {
            "status": "READY" if (bids or asks) else "NO_DATA",
            "pair": pair,
            "mid": mid,
            "spread": spread,
            "bids": bids,
            "asks": asks,
            "provider": provider,
            "note": (
                "Only the live top-of-book quote is shown (size/total columns "
                "are not applicable) -- no broker/ECN market-depth (L2) feed "
                "is connected yet."
            ),
            "generated_at": _utc_iso(),
        }


_BOOK = None


def get_forex_order_book(db: Optional[Any] = None) -> ForexOrderBook:
    global _BOOK
    if _BOOK is None or (db is not None and _BOOK.db is None):
        _BOOK = ForexOrderBook(db=db)
    return _BOOK