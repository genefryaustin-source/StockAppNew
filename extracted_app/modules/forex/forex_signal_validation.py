"""
modules/forex/forex_signal_validation.py

Phase 14A — Signal validation and scoring.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


class ForexSignalValidation:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def validate_signal(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        score = float(signal.get("alpha_score") or signal.get("confidence") or 0)
        errors = []
        warnings = []
        if not signal.get("pair"):
            errors.append("Missing pair.")
        if score < 55:
            warnings.append("Signal score below preferred research threshold.")
        approved = len(errors) == 0 and score >= 50
        return {
            "approved": approved,
            "validation_score": round(score, 2),
            "errors": errors,
            "warnings": warnings,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def validate_batch(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        ideas = payload.get("ideas") or payload.get("signals") or []
        rows = [{"signal": idea, "validation": self.validate_signal(idea)} for idea in ideas]
        return {
            "status": "READY",
            "count": len(rows),
            "approved_count": sum(1 for r in rows if r["validation"]["approved"]),
            "rows": rows,
        }


_VALIDATOR = None


def get_forex_signal_validation(db: Optional[Any] = None) -> ForexSignalValidation:
    global _VALIDATOR
    if _VALIDATOR is None or (db is not None and _VALIDATOR.db is None):
        _VALIDATOR = ForexSignalValidation(db=db)
    return _VALIDATOR
