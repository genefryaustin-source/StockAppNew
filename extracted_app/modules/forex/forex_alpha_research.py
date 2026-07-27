"""
modules/forex/forex_alpha_research.py

Phase 14A — Alpha research engine.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


class ForexAlphaResearch:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def discover_alpha(self, limit: int = 12) -> Dict[str, Any]:
        from modules.forex.forex_factor_models import get_forex_factor_models
        factors = get_forex_factor_models(db=self.db).factor_snapshot()
        ideas = []
        for row in factors["rows"][:limit]:
            score = row["composite_factor_score"]
            ideas.append({
                "pair": row["pair"],
                "signal": "BUY" if score >= 60 else "SELL" if score <= 40 else "WATCH",
                "alpha_score": score,
                "factor_stack": row,
                "hypothesis": f"{row['pair']} shows {row['bias']} factor alignment.",
                "research_status": "candidate",
            })
        return {
            "status": "READY",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "alpha_count": len(ideas),
            "ideas": ideas,
        }


_ALPHA = None


def get_forex_alpha_research(db: Optional[Any] = None) -> ForexAlphaResearch:
    global _ALPHA
    if _ALPHA is None or (db is not None and _ALPHA.db is None):
        _ALPHA = ForexAlphaResearch(db=db)
    return _ALPHA
