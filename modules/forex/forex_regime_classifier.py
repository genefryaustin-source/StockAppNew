"""
modules/forex/forex_regime_classifier.py

Phase 14A — FX regime classifier.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


class ForexRegimeClassifier:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def classify(self, snapshot: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        snapshot = snapshot or {}
        risk = snapshot.get("risk") or {}
        perf = snapshot.get("performance") or {}
        score = 50.0
        score += min(20.0, float(perf.get("total_pnl") or 0) / 1000.0)
        score -= min(20.0, float(risk.get("risk_score") or 75) < 50 and 20 or 0)
        regime = "RISK_ON" if score >= 60 else "RISK_OFF" if score <= 40 else "NEUTRAL"
        return {
            "status": "READY",
            "regime": regime,
            "confidence": round(abs(score - 50) * 2, 2),
            "score": round(score, 2),
            "drivers": [
                "portfolio_pnl",
                "risk_score",
                "currency_strength",
                "macro_conditions",
            ],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


_CLASSIFIER = None


def get_forex_regime_classifier(db: Optional[Any] = None) -> ForexRegimeClassifier:
    global _CLASSIFIER
    if _CLASSIFIER is None or (db is not None and _CLASSIFIER.db is None):
        _CLASSIFIER = ForexRegimeClassifier(db=db)
    return _CLASSIFIER
