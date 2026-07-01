"""
modules/forex/forex_reversal_scanner.py

Phase 18C — Reversal Scanner.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


class ForexReversalScanner:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def scan(self, pairs=None) -> Dict[str, Any]:
        pairs = pairs or ["EUR/USD", "USD/JPY", "GBP/USD", "AUD/USD", "USD/CAD", "EUR/JPY"]
        rows = []
        for pair in pairs:
            score = (abs(hash("reversal" + pair)) % 1000) / 10
            rows.append({
                "pair": pair,
                "setup": "REVERSAL",
                "score": round(score, 2),
                "signal": "BUY" if score >= 66 else "SELL" if score <= 33 else "WATCH",
                "confidence": round(max(score, 100-score), 2),
            })
        rows.sort(key=lambda r: r["confidence"], reverse=True)
        return {
            "status": "READY",
            "scanner": "REVERSAL",
            "rows": rows,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


_ENGINE = None


def get_forex_reversal_scanner(db: Optional[Any] = None) -> ForexReversalScanner:
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None):
        _ENGINE = ForexReversalScanner(db=db)
    return _ENGINE
