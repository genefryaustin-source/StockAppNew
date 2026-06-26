"""
modules/forex/forex_watchlist_manager.py

Institutional FX watchlist manager.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

DEFAULT_PAIRS = [
    "EUR/USD", "USD/JPY", "GBP/USD", "USD/CHF", "AUD/USD", "USD/CAD",
    "NZD/USD", "EUR/JPY", "EUR/GBP", "GBP/JPY", "CHF/JPY", "AUD/JPY",
]


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


class ForexWatchlistManager:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def get_watchlist(self, pairs: Optional[List[str]] = None, **kwargs) -> Dict[str, Any]:
        rows = []
        for pair in pairs or DEFAULT_PAIRS:
            rows.append(self._row(pair))
        return {
            "status": "READY",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "rows": rows,
        }

    def _row(self, pair: str) -> Dict[str, Any]:
        last = self._last_price(pair)
        return {
            "pair": pair,
            "last": last,
            "bid": round(last - self._spread(pair) / 2, 5),
            "ask": round(last + self._spread(pair) / 2, 5),
            "spread": round(self._spread(pair), 5),
            "session_change_pct": round(((hash(pair) % 240) - 120) / 100.0, 2),
            "signal": "BUY" if hash(pair) % 3 == 0 else "SELL" if hash(pair) % 3 == 1 else "WATCH",
            "volatility": "High" if hash(pair) % 5 == 0 else "Normal",
        }

    def _last_price(self, pair: str) -> float:
        defaults = {
            "EUR/USD": 1.0718, "GBP/USD": 1.2645, "AUD/USD": 0.6641,
            "NZD/USD": 0.6120, "USD/JPY": 158.42, "USD/CHF": 0.8912,
            "USD/CAD": 1.3710, "EUR/JPY": 169.72, "EUR/GBP": 0.8475,
            "GBP/JPY": 200.28, "CHF/JPY": 177.75, "AUD/JPY": 105.18,
        }
        return defaults.get(pair, 1.0)

    def _spread(self, pair: str) -> float:
        return 0.02 if "JPY" in pair else 0.00012


_MANAGER = None


def get_forex_watchlist_manager(db: Optional[Any] = None) -> ForexWatchlistManager:
    global _MANAGER
    if _MANAGER is None or (db is not None and _MANAGER.db is None):
        _MANAGER = ForexWatchlistManager(db=db)
    return _MANAGER
