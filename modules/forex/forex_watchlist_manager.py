"""
modules/forex/forex_watchlist_manager.py

Institutional FX watchlist manager.

Previously every row here came from a hardcoded per-pair price dict
("EUR/USD": 1.0718, "USD/JPY": 158.42, ...), and session_change_pct/
signal/volatility were derived from Python's hash() of the pair string --
a deterministic fingerprint that has nothing to do with real market data.

This now pulls a live top-of-book quote (bid/ask/mid/spread) from the real
provider pipeline for "last", and computes session_change_pct/volatility
from live intraday history. "signal" is a simple, honest momentum read off
that same real change_pct -- not a hash-based coin flip. When no live quote
or history is available for a pair, the row reports None/"-"/"NO_DATA"
instead of a fabricated number.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

DEFAULT_PAIRS = [
    "EUR/USD", "USD/JPY", "GBP/USD", "USD/CHF", "AUD/USD", "USD/CAD",
    "NZD/USD", "EUR/JPY", "EUR/GBP", "GBP/JPY", "CHF/JPY", "AUD/JPY",
]


def _safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


class ForexWatchlistManager:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def get_watchlist(self, pairs: Optional[List[str]] = None, **kwargs) -> Dict[str, Any]:
        rows = []
        any_live = False
        for pair in pairs or DEFAULT_PAIRS:
            row = self._row(pair)
            if row.get("status") == "LIVE":
                any_live = True
            rows.append(row)
        return {
            "status": "READY" if any_live else "NO_DATA",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "rows": rows,
        }

    def _row(self, pair: str) -> Dict[str, Any]:
        quote = self._quote(pair)
        if not quote:
            return {
                "pair": pair,
                "last": None,
                "bid": None,
                "ask": None,
                "spread": None,
                "session_change_pct": None,
                "signal": "WATCH",
                "volatility": "-",
                "status": "NO_DATA",
                "note": "No live quote available for this pair.",
            }

        last = quote.get("mid") or quote.get("last")
        bid = quote.get("bid")
        ask = quote.get("ask")
        spread = quote.get("spread")
        change_pct, vol_label = self._session_stats(pair, last)
        signal = self._signal(change_pct)

        return {
            "pair": pair,
            "last": last,
            "bid": bid,
            "ask": ask,
            "spread": spread,
            "session_change_pct": change_pct,
            "signal": signal,
            "volatility": vol_label,
            "status": "LIVE",
            "provider": quote.get("provider") or quote.get("source") or "-",
        }

    def _quote(self, pair: str) -> Optional[Dict[str, Any]]:
        try:
            from modules.forex.forex_price_service import get_forex_price_service
            quote = get_forex_price_service().get_quote(pair)
        except Exception:
            return None
        if not isinstance(quote, dict) or quote.get("error"):
            return None
        return quote

    def _session_stats(self, pair: str, last: Optional[float]):
        """
        Real session change % and a volatility bucket, both computed from
        live intraday history bars -- not derived from hash(pair).
        """
        try:
            from modules.forex.forex_history_service import get_forex_history_service
            payload = get_forex_history_service().fetch_from_router(pair, interval="1h")
        except Exception:
            return None, "-"

        rows = payload.get("rows") if isinstance(payload, dict) else None
        if not rows or len(rows) < 2:
            return None, "-"

        closes = [c for c in (_safe_float(r.get("close")) for r in rows) if c is not None]
        if len(closes) < 2:
            return None, "-"

        session_open = closes[0]
        current = last if last is not None else closes[-1]
        change_pct = None
        if session_open:
            change_pct = round(((current - session_open) / session_open) * 100, 2)

        returns = []
        for i in range(1, len(closes)):
            prev = closes[i - 1]
            if prev:
                returns.append((closes[i] - prev) / prev)

        vol_label = "-"
        if len(returns) >= 5:
            mean = sum(returns) / len(returns)
            variance = sum((r - mean) ** 2 for r in returns) / len(returns)
            stdev = variance ** 0.5
            vol_label = "High" if stdev > 0.0025 else "Normal" if stdev > 0.0008 else "Low"

        return change_pct, vol_label

    def _signal(self, change_pct: Optional[float]) -> str:
        if change_pct is None:
            return "WATCH"
        if change_pct >= 0.15:
            return "BUY"
        if change_pct <= -0.15:
            return "SELL"
        return "WATCH"


_MANAGER = None


def get_forex_watchlist_manager(db: Optional[Any] = None) -> ForexWatchlistManager:
    global _MANAGER
    if _MANAGER is None or (db is not None and _MANAGER.db is None):
        _MANAGER = ForexWatchlistManager(db=db)
    return _MANAGER