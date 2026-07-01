"""
modules/forex/forex_opportunity_scanner.py

Phase 18C — Institutional opportunity scanner.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


class ForexOpportunityScanner:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def scan(self, pairs=None) -> Dict[str, Any]:
        from modules.forex.forex_breakout_scanner import get_forex_breakout_scanner
        from modules.forex.forex_reversal_scanner import get_forex_reversal_scanner
        from modules.forex.forex_mean_reversion_scanner import get_forex_mean_reversion_scanner
        from modules.forex.forex_trend_scanner import get_forex_trend_scanner

        scanners = [
            get_forex_breakout_scanner(db=self.db).scan(pairs),
            get_forex_reversal_scanner(db=self.db).scan(pairs),
            get_forex_mean_reversion_scanner(db=self.db).scan(pairs),
            get_forex_trend_scanner(db=self.db).scan(pairs),
        ]

        rows = []
        for scanner in scanners:
            rows.extend(scanner.get("rows", []))

        rows.sort(key=lambda r: r.get("confidence", 0), reverse=True)

        return {
            "status": "READY",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "opportunity_count": len(rows),
            "opportunities": rows,
            "top_opportunity": rows[0] if rows else {},
            "scanner_payloads": scanners,
        }


_ENGINE = None


def get_forex_opportunity_scanner(db: Optional[Any] = None) -> ForexOpportunityScanner:
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None):
        _ENGINE = ForexOpportunityScanner(db=db)
    return _ENGINE
