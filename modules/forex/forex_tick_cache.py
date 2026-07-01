"""
modules/forex/forex_tick_cache.py

Phase 16A — Lightweight in-memory tick cache.
"""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class ForexTickCache:
    def __init__(self, db: Optional[Any] = None, maxlen: int = 5000):
        self.db = db
        self.maxlen = maxlen
        self._ticks = defaultdict(lambda: deque(maxlen=maxlen))

    def add_tick(self, pair: str, quote: Dict[str, Any]) -> Dict[str, Any]:
        row = dict(quote or {})
        row.setdefault("pair", pair)
        row.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        self._ticks[pair].append(row)
        return row

    def recent(self, pair: str, limit: int = 250) -> List[Dict[str, Any]]:
        rows = list(self._ticks[pair])
        return rows[-int(limit):]

    def summary(self) -> Dict[str, Any]:
        return {
            "status": "READY",
            "pairs": len(self._ticks),
            "tick_counts": {pair: len(rows) for pair, rows in self._ticks.items()},
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


_CACHE = None


def get_forex_tick_cache(db: Optional[Any] = None) -> ForexTickCache:
    global _CACHE
    if _CACHE is None:
        _CACHE = ForexTickCache(db=db)
    return _CACHE
