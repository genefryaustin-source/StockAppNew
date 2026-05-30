"""
modules/analytics/adaptive_factor_engine.py

Adaptive factor intelligence engine.

Phase 1:
- market regime detection
- adaptive factor weights
- realized-return learning hooks
- analyst override learning hooks
- AI score adjustment support

This does NOT replace the existing ranking engine.
It provides adaptive weights and overlays that can be wired into
ai_ranking_engine.py later.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Any, Dict, List, Optional
import math


# ---------------------------------------------------
# DATA MODELS
# ---------------------------------------------------

@dataclass
class MarketRegime:
    regime: str
    confidence: float
    volatility_level: str
    momentum_state: str
    risk_state: str
    detected_at: datetime


@dataclass
class AdaptiveWeights:
    quality: float
    growth: float
    value: float
    momentum: float
    risk: float
    sentiment: float
    earnings_nlp: float
    confidence: float
    regime: str
    updated_at: datetime


@dataclass
class LearningEvent:
    symbol: str
    original_rank: Optional[int]
    original_score: Optional[float]
    realized_return: Optional[float]
    benchmark_return: Optional[float]
    analyst_override: Optional[str] = None
    outcome: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------
# HELPERS
# ---------------------------------------------------

def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default

        value = float(value)

        if math.isnan(value) or math.isinf(value):
            return default

        return value

    except Exception:
        return default


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


# ---------------------------------------------------
# MARKET REGIME DETECTION
# ---------------------------------------------------

def detect_market_regime(
    market_return_30d: float = 0.0,
    market_return_90d: float = 0.0,
    volatility_30d: float = 0.0,
    drawdown_90d: float = 0.0,
) -> MarketRegime:

    r30 = _safe_float(market_return_30d)
    r90 = _safe_float(market_return_90d)
    vol = _safe_float(volatility_30d)
    dd = _safe_float(drawdown_90d)

    if dd <= -0.15 or vol >= 0.35:
        regime = "panic"
        risk_state = "high"
    elif r90 < -0.08:
        regime = "bear"
        risk_state = "elevated"
    elif r30 > 0.04 and r90 > 0.08:
        regime = "bull"
        risk_state = "normal"
    elif abs(r30) < 0.03 and vol < 0.18:
        regime = "range_bound"
        risk_state = "normal"
    elif r30 > 0.03 and vol > 0.25:
        regime = "momentum_volatility"
        risk_state = "elevated"
    else:
        regime = "neutral"
        risk_state = "normal"

    if vol >= 0.35:
        volatility_level = "extreme"
    elif vol >= 0.25:
        volatility_level = "high"
    elif vol >= 0.15:
        volatility_level = "moderate"
    else:
        volatility_level = "low"

    if r30 > 0.04:
        momentum_state = "positive"
    elif r30 < -0.04:
        momentum_state = "negative"
    else:
        momentum_state = "mixed"

    confidence = 60.0

    if regime in {"panic", "bull", "bear"}:
        confidence += 20.0

    if volatility_level in {"extreme", "high"}:
        confidence += 10.0

    confidence = min(100.0, confidence)

    return MarketRegime(
        regime=regime,
        confidence=round(confidence, 2),
        volatility_level=volatility_level,
        momentum_state=momentum_state,
        risk_state=risk_state,
        detected_at=datetime.now(UTC),
    )


# ---------------------------------------------------
# ADAPTIVE WEIGHT COMPUTATION
# ---------------------------------------------------

def compute_adaptive_weights(
    regime: Optional[MarketRegime] = None,
    learning_bias: Optional[Dict[str, float]] = None,
) -> AdaptiveWeights:

    if regime is None:
        regime = detect_market_regime()

    weights = {
        "quality": 0.10,
        "growth": 0.08,
        "value": 0.07,
        "momentum": 0.10,
        "risk": 0.08,
        "sentiment": 0.07,
        "earnings_nlp": 0.07,
        "confidence": 0.05,
    }

    if regime.regime == "bull":
        weights["growth"] += 0.03
        weights["momentum"] += 0.03
        weights["risk"] -= 0.02

    elif regime.regime == "bear":
        weights["quality"] += 0.04
        weights["risk"] += 0.04
        weights["value"] += 0.02
        weights["growth"] -= 0.03
        weights["momentum"] -= 0.02

    elif regime.regime == "panic":
        weights["quality"] += 0.05
        weights["risk"] += 0.06
        weights["confidence"] += 0.03
        weights["growth"] -= 0.04
        weights["sentiment"] -= 0.02

    elif regime.regime == "momentum_volatility":
        weights["momentum"] += 0.04
        weights["risk"] += 0.03
        weights["sentiment"] += 0.02

    elif regime.regime == "range_bound":
        weights["value"] += 0.03
        weights["quality"] += 0.02
        weights["momentum"] -= 0.02

    if learning_bias:
        for key, value in learning_bias.items():
            if key in weights:
                weights[key] += _safe_float(value)

    for key in weights:
        weights[key] = round(_clamp(weights[key], 0.0, 0.25), 4)

    return AdaptiveWeights(
        quality=weights["quality"],
        growth=weights["growth"],
        value=weights["value"],
        momentum=weights["momentum"],
        risk=weights["risk"],
        sentiment=weights["sentiment"],
        earnings_nlp=weights["earnings_nlp"],
        confidence=weights["confidence"],
        regime=regime.regime,
        updated_at=datetime.now(UTC),
    )


# ---------------------------------------------------
# LEARNING FROM OUTCOMES
# ---------------------------------------------------

def learn_from_realized_returns(
    events: List[LearningEvent],
) -> Dict[str, float]:

    if not events:
        return {}

    alpha_sum = 0.0
    count = 0

    winners = 0
    losers = 0

    for event in events:
        rr = _safe_float(event.realized_return)
        br = _safe_float(event.benchmark_return)

        alpha = rr - br

        alpha_sum += alpha
        count += 1

        if alpha > 0:
            winners += 1
        elif alpha < 0:
            losers += 1

    if count == 0:
        return {}

    avg_alpha = alpha_sum / count
    win_rate = winners / count

    bias = {}

    if avg_alpha > 0.03 and win_rate >= 0.55:
        bias["momentum"] = 0.015
        bias["growth"] = 0.01
        bias["confidence"] = 0.005

    elif avg_alpha < -0.03:
        bias["risk"] = 0.02
        bias["quality"] = 0.015
        bias["sentiment"] = -0.01

    if losers > winners:
        bias["risk"] = bias.get("risk", 0.0) + 0.01
        bias["confidence"] = bias.get("confidence", 0.0) + 0.005

    return bias


def learn_from_analyst_overrides(
    events: List[LearningEvent],
) -> Dict[str, float]:

    if not events:
        return {}

    bias = {}

    rejected = [
        e for e in events
        if str(e.analyst_override or "").lower() in {"reject", "rejected", "avoid"}
    ]

    approved = [
        e for e in events
        if str(e.analyst_override or "").lower() in {"approve", "approved", "accept"}
    ]

    if len(rejected) > len(approved):
        bias["risk"] = 0.015
        bias["confidence"] = 0.01

    if len(approved) > len(rejected):
        bias["momentum"] = 0.01
        bias["sentiment"] = 0.005

    return bias


# ---------------------------------------------------
# AI SCORE ADJUSTMENT
# ---------------------------------------------------

def adaptive_score_adjustment(
    base_ai_score: float,
    factor_values: Dict[str, Any],
    weights: AdaptiveWeights,
) -> float:

    score = _safe_float(base_ai_score, 50.0)

    quality = _safe_float(factor_values.get("quality"), 50.0)
    growth = _safe_float(factor_values.get("growth"), 50.0)
    value = _safe_float(factor_values.get("value"), 50.0)
    momentum = _safe_float(factor_values.get("momentum"), 50.0)
    risk = _safe_float(factor_values.get("risk"), 50.0)
    sentiment = _safe_float(factor_values.get("sentiment"), 0.0)
    earnings_nlp = _safe_float(factor_values.get("earnings_nlp"), 0.0)
    confidence = _safe_float(factor_values.get("confidence"), 50.0)

    score += (quality - 50.0) * weights.quality
    score += (growth - 50.0) * weights.growth
    score += (value - 50.0) * weights.value
    score += (momentum - 50.0) * weights.momentum
    score += (50.0 - risk) * weights.risk
    score += sentiment * 10.0 * weights.sentiment
    score += earnings_nlp * 10.0 * weights.earnings_nlp
    score += (confidence - 50.0) * weights.confidence

    return round(max(0.0, min(100.0, score)), 4)


# ---------------------------------------------------
# EXPORT
# ---------------------------------------------------

def adaptive_weights_to_dict(
    weights: AdaptiveWeights,
) -> Dict[str, Any]:

    return {
        "quality": weights.quality,
        "growth": weights.growth,
        "value": weights.value,
        "momentum": weights.momentum,
        "risk": weights.risk,
        "sentiment": weights.sentiment,
        "earnings_nlp": weights.earnings_nlp,
        "confidence": weights.confidence,
        "regime": weights.regime,
        "updated_at": weights.updated_at,
    }