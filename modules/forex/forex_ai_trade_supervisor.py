"""
modules/forex/forex_ai_trade_supervisor.py

Phase 11 AI trade supervisor.
"""

from __future__ import annotations

from typing import Any, Dict


def _f(x, d=0.0):
    try:
        return float(x)
    except Exception:
        return d


class ForexAITradeSupervisor:
    def __init__(self, db=None):
        self.db = db

    def review_trade(self, candidate: Dict[str, Any], snapshot: Dict[str, Any]) -> Dict[str, Any]:
        confidence = _f(candidate.get("confidence"))
        rr = _f(candidate.get("risk_reward"))
        side = candidate.get("side")
        pair = candidate.get("pair")
        errors = []
        warnings = []
        if confidence < 75:
            errors.append("Confidence below minimum threshold.")
        if rr and rr < 1.2:
            warnings.append("Risk/reward below preferred institutional threshold.")
        if not pair or not side:
            errors.append("Missing pair or side.")
        return {
            "approved": len(errors) == 0,
            "quality_score": round(max(0, min(100, confidence + min(rr, 3) * 5 - len(warnings) * 5)), 2),
            "errors": errors,
            "warnings": warnings,
            "explanation": f"{pair} {side} reviewed with confidence {confidence:.0f} and RR {rr:.2f}.",
            "hedge_suggestion": self._hedge(pair, side),
        }

    def _hedge(self, pair, side):
        if not pair:
            return None
        if "JPY" in pair:
            return "Monitor correlated JPY exposure."
        if "USD" in pair:
            return "Check aggregate USD exposure before execution."
        return "No immediate hedge suggestion."


_SUP = None


def get_forex_ai_trade_supervisor(db=None):
    global _SUP
    if _SUP is None or (db is not None and _SUP.db is None):
        _SUP = ForexAITradeSupervisor(db=db)
    return _SUP
