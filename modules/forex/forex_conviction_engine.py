"""
modules/forex/forex_conviction_engine.py

Phase 18A — Conviction engine.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


class ForexConvictionEngine:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def conviction(self, score: Dict[str, Any]) -> Dict[str, Any]:
        institutional_score = float(score.get("institutional_score") or 0)
        alignment = 0
        for key in ["quant_score", "macro_score", "flow_score", "ai_score", "risk_score"]:
            if float(score.get(key) or 0) >= 65:
                alignment += 1

        conviction = institutional_score * 0.75 + alignment * 5
        conviction = max(0, min(100, conviction))

        return {
            "status": "READY",
            "pair": score.get("pair"),
            "conviction_score": round(conviction, 2),
            "alignment_count": alignment,
            "conviction_band": "HIGH" if conviction >= 80 else "MEDIUM" if conviction >= 60 else "LOW",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


_ENGINE = None


def get_forex_conviction_engine(db: Optional[Any] = None) -> ForexConvictionEngine:
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None):
        _ENGINE = ForexConvictionEngine(db=db)
    return _ENGINE
