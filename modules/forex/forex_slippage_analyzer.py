"""
modules/forex/forex_slippage_analyzer.py

Phase 20C — Slippage analyzer.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


class ForexSlippageAnalyzer:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def analyze(self) -> Dict[str, Any]:
        return {
            "status": "READY",
            "avg_slippage_pips": 0.0,
            "p95_slippage_pips": 0.0,
            "message": "Paper fills currently assume zero slippage unless configured.",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


_ENGINE = None


def get_forex_slippage_analyzer(db: Optional[Any] = None) -> ForexSlippageAnalyzer:
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None):
        _ENGINE = ForexSlippageAnalyzer(db=db)
    return _ENGINE
