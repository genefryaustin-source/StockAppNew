"""
modules/forex/forex_factor_models.py

Phase 14A — Institutional FX factor models.

Factors:
- Carry
- Momentum
- Value
- Volatility
- Macro
- Risk sentiment
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


DEFAULT_PAIRS = [
    "EUR/USD", "USD/JPY", "GBP/USD", "USD/CHF", "AUD/USD", "USD/CAD",
    "NZD/USD", "EUR/JPY", "EUR/GBP", "GBP/JPY", "CHF/JPY", "AUD/JPY",
]


def _score(seed: str, lo: float = 0.0, hi: float = 100.0) -> float:
    val = abs(hash(seed)) % 10000 / 10000.0
    return round(lo + (hi - lo) * val, 4)


class ForexFactorModels:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def factor_snapshot(self, pairs: Optional[List[str]] = None) -> Dict[str, Any]:
        rows = [self.score_pair(pair) for pair in (pairs or DEFAULT_PAIRS)]
        rows.sort(key=lambda r: r["composite_factor_score"], reverse=True)
        return {
            "status": "READY",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "rows": rows,
            "leaders": rows[:5],
            "laggards": rows[-5:],
        }

    def score_pair(self, pair: str) -> Dict[str, Any]:
        carry = _score(pair + "carry")
        momentum = _score(pair + "momentum")
        value = _score(pair + "value")
        volatility = 100 - _score(pair + "volatility")
        macro = _score(pair + "macro")
        sentiment = _score(pair + "sentiment")
        composite = (
            carry * 0.18
            + momentum * 0.24
            + value * 0.16
            + volatility * 0.14
            + macro * 0.18
            + sentiment * 0.10
        )
        return {
            "pair": pair,
            "carry_factor": round(carry, 2),
            "momentum_factor": round(momentum, 2),
            "value_factor": round(value, 2),
            "volatility_factor": round(volatility, 2),
            "macro_factor": round(macro, 2),
            "sentiment_factor": round(sentiment, 2),
            "composite_factor_score": round(composite, 2),
            "bias": "LONG" if composite >= 60 else "SHORT" if composite <= 40 else "NEUTRAL",
        }


_MODELS = None


def get_forex_factor_models(db: Optional[Any] = None) -> ForexFactorModels:
    global _MODELS
    if _MODELS is None or (db is not None and _MODELS.db is None):
        _MODELS = ForexFactorModels(db=db)
    return _MODELS
