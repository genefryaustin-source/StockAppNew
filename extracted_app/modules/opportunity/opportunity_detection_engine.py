"""
modules/opportunity/opportunity_detection_engine.py

Autonomous opportunity detection engine.

Detects:
- capitulation recovery
- institutional accumulation
- volatility dislocations
- sentiment inflections
- momentum recoveries
- asymmetric risk/reward setups

Phase 1:
- OpportunitySignal model
- detect_opportunity_signals()
- detect_institutional_accumulation()
- rank_asymmetric_opportunities()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Any, Dict, List, Optional
import math


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


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


# ---------------------------------------------------
# OPPORTUNITY MODEL
# ---------------------------------------------------

@dataclass
class OpportunitySignal:
    symbol: str

    opportunity_type: str
    confidence: float
    asymmetry_score: float
    recovery_probability: float
    risk_reward_ratio: float
    signal_strength: float

    market_regime: str = "neutral"

    rationale: str = ""

    warnings: List[str] = field(default_factory=list)
    signals: List[str] = field(default_factory=list)

    metadata: Dict[str, Any] = field(default_factory=dict)

    generated_at: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "opportunity_type": self.opportunity_type,
            "confidence": round(self.confidence, 4),
            "asymmetry_score": round(self.asymmetry_score, 4),
            "recovery_probability": round(self.recovery_probability, 4),
            "risk_reward_ratio": round(self.risk_reward_ratio, 4),
            "signal_strength": round(self.signal_strength, 4),
            "market_regime": self.market_regime,
            "rationale": self.rationale,
            "warnings": self.warnings,
            "signals": self.signals,
            "metadata": self.metadata,
            "generated_at": self.generated_at,
        }


# ---------------------------------------------------
# INSTITUTIONAL ACCUMULATION
# ---------------------------------------------------

def detect_institutional_accumulation(
    symbol: str,
    ai_score: float = 50.0,
    sentiment_score: float = 0.0,
    momentum: float = 50.0,
    volatility: float = 25.0,
    drawdown: float = 0.0,
    volume_pressure: float = 50.0,
    market_regime: str = "neutral",
) -> Optional[OpportunitySignal]:

    ai_score = _safe_float(ai_score, 50.0)
    sentiment_score = _safe_float(sentiment_score, 0.0)
    momentum = _safe_float(momentum, 50.0)
    volatility = _safe_float(volatility, 25.0)
    drawdown = abs(_safe_float(drawdown, 0.0))
    volume_pressure = _safe_float(volume_pressure, 50.0)

    signals = []
    warnings = []

    score = 0.0

    if ai_score >= 65:
        score += 25
        signals.append("strong AI conviction")

    if momentum >= 55:
        score += 18
        signals.append("momentum stabilization")

    if sentiment_score > 0:
        score += 15
        signals.append("positive sentiment inflection")

    if volume_pressure >= 60:
        score += 18
        signals.append("accumulation volume pressure")

    if 8 <= drawdown <= 35:
        score += 12
        signals.append("recoverable drawdown range")

    if volatility <= 45:
        score += 12
        signals.append("volatility remains manageable")
    else:
        warnings.append("elevated volatility may impair accumulation signal")

    confidence = _clamp(score)

    if confidence < 55:
        return None

    asymmetry = _clamp(
        (ai_score * 0.35)
        + (momentum * 0.25)
        + (volume_pressure * 0.20)
        + ((100.0 - volatility) * 0.20)
    )

    recovery_probability = _clamp(
        45.0
        + ((ai_score - 50.0) * 0.35)
        + ((momentum - 50.0) * 0.25)
        + (sentiment_score * 20.0)
    )

    risk_reward_ratio = round(
        max(0.5, asymmetry / max(10.0, volatility)),
        4,
    )

    rationale = (
        f"{symbol} shows potential institutional accumulation. "
        f"AI score={round(ai_score, 2)}, momentum={round(momentum, 2)}, "
        f"sentiment={round(sentiment_score, 2)}, volatility={round(volatility, 2)}, "
        f"drawdown={round(drawdown, 2)}."
    )

    return OpportunitySignal(
        symbol=symbol,
        opportunity_type="Institutional Accumulation",
        confidence=confidence,
        asymmetry_score=asymmetry,
        recovery_probability=recovery_probability,
        risk_reward_ratio=risk_reward_ratio,
        signal_strength=confidence,
        market_regime=market_regime,
        rationale=rationale,
        warnings=warnings,
        signals=signals,
        metadata={
            "ai_score": ai_score,
            "sentiment_score": sentiment_score,
            "momentum": momentum,
            "volatility": volatility,
            "drawdown": drawdown,
            "volume_pressure": volume_pressure,
        },
    )


# ---------------------------------------------------
# OPPORTUNITY DETECTION
# ---------------------------------------------------

def detect_opportunity_signals(
    rows: List[Any],
    sentiment_overlay: Optional[Dict[str, float]] = None,
    market_regime: str = "neutral",
    predictive_forecast: Optional[Any] = None,
    max_results: int = 25,
) -> List[OpportunitySignal]:

    if not rows:
        return []

    sentiment_overlay = sentiment_overlay or {}

    forecast_regime = getattr(
        predictive_forecast,
        "predicted_regime",
        market_regime,
    )

    forecast_stress = _safe_float(
        getattr(
            predictive_forecast,
            "stress_forecast",
            50.0,
        ),
        50.0,
    )

    results: List[OpportunitySignal] = []

    for row in rows:

        symbol = str(getattr(row, "symbol", "")).upper()

        if not symbol:
            continue

        ai_score = _safe_float(
            getattr(row, "ai_score", None),
            _safe_float(getattr(row, "composite", None), 50.0),
        )

        confidence = _safe_float(
            getattr(row, "ai_confidence", None),
            _safe_float(getattr(row, "confidence", None), 50.0),
        )

        momentum = _safe_float(
            getattr(row, "momentum", None),
            50.0,
        )

        risk = _safe_float(
            getattr(row, "risk", None),
            50.0,
        )

        volatility = _safe_float(
            getattr(row, "volatility", None),
            risk,
        )

        sentiment_score = _safe_float(
            sentiment_overlay.get(symbol, 0.0),
            0.0,
        )

        drawdown = _safe_float(
            getattr(row, "drawdown", None),
            0.0,
        )

        signals = []
        warnings = []

        opportunity_type = "Asymmetric AI Opportunity"

        base_score = 0.0

        # -----------------------------------
        # CAPITULATION RECOVERY
        # -----------------------------------

        if (
            forecast_regime in {"panic", "bear"}
            or forecast_stress >= 65
        ) and ai_score >= 60:

            base_score += 25
            opportunity_type = "Capitulation Recovery"
            signals.append("AI conviction remains constructive during stress")

        # -----------------------------------
        # SENTIMENT INFLECTION
        # -----------------------------------

        if sentiment_score > 0.15:
            base_score += 18
            signals.append("positive sentiment inflection")

        elif sentiment_score < -0.15:
            warnings.append("negative sentiment pressure")

        # -----------------------------------
        # MOMENTUM RECOVERY
        # -----------------------------------

        if momentum >= 60:
            base_score += 20
            signals.append("momentum recovery detected")

        elif momentum < 40:
            warnings.append("weak momentum")

        # -----------------------------------
        # RISK / VOLATILITY
        # -----------------------------------

        if risk <= 45:
            base_score += 15
            signals.append("risk profile controlled")

        elif risk >= 70:
            base_score -= 20
            warnings.append("elevated risk")

        if volatility <= 45:
            base_score += 10
            signals.append("volatility manageable")

        elif volatility >= 70:
            base_score -= 15
            warnings.append("extreme volatility")

        # -----------------------------------
        # CONFIDENCE
        # -----------------------------------

        if confidence >= 65:
            base_score += 15
            signals.append("high AI confidence")

        # -----------------------------------
        # SCORE OUTPUT
        # -----------------------------------

        asymmetry_score = _clamp(
            base_score
            + (ai_score * 0.35)
            + (confidence * 0.20)
        )

        recovery_probability = _clamp(
            40.0
            + ((ai_score - 50.0) * 0.35)
            + ((momentum - 50.0) * 0.25)
            + (sentiment_score * 25.0)
            - max(0.0, risk - 50.0) * 0.20
        )

        risk_reward_ratio = round(
            max(
                0.5,
                asymmetry_score / max(10.0, risk),
            ),
            4,
        )

        signal_strength = _clamp(
            (asymmetry_score * 0.45)
            + (recovery_probability * 0.35)
            + (confidence * 0.20)
        )

        if signal_strength < 50:
            continue

        rationale = (
            f"{symbol} detected as {opportunity_type}. "
            f"AI score={round(ai_score, 2)}, confidence={round(confidence, 2)}, "
            f"momentum={round(momentum, 2)}, risk={round(risk, 2)}, "
            f"sentiment overlay={round(sentiment_score, 4)}."
        )

        results.append(
            OpportunitySignal(
                symbol=symbol,
                opportunity_type=opportunity_type,
                confidence=confidence,
                asymmetry_score=asymmetry_score,
                recovery_probability=recovery_probability,
                risk_reward_ratio=risk_reward_ratio,
                signal_strength=signal_strength,
                market_regime=market_regime,
                rationale=rationale,
                warnings=warnings,
                signals=signals,
                metadata={
                    "ai_score": ai_score,
                    "confidence": confidence,
                    "momentum": momentum,
                    "risk": risk,
                    "volatility": volatility,
                    "sentiment_score": sentiment_score,
                    "forecast_regime": forecast_regime,
                    "forecast_stress": forecast_stress,
                    "drawdown": drawdown,
                },
            )
        )

        accumulation = detect_institutional_accumulation(
            symbol=symbol,
            ai_score=ai_score,
            sentiment_score=sentiment_score,
            momentum=momentum,
            volatility=volatility,
            drawdown=drawdown,
            volume_pressure=50.0,
            market_regime=market_regime,
        )

        if accumulation:
            results.append(accumulation)

    return rank_asymmetric_opportunities(
        results,
        max_results=max_results,
    )


# ---------------------------------------------------
# RANK OPPORTUNITIES
# ---------------------------------------------------

def rank_asymmetric_opportunities(
    opportunities: List[OpportunitySignal],
    max_results: int = 25,
) -> List[OpportunitySignal]:

    if not opportunities:
        return []

    ranked = sorted(
        opportunities,
        key=lambda x: (
            x.asymmetry_score,
            x.recovery_probability,
            x.risk_reward_ratio,
            x.confidence,
        ),
        reverse=True,
    )

    return ranked[:max_results]


# ---------------------------------------------------
# DATAFRAME EXPORT
# ---------------------------------------------------

def opportunities_to_dataframe(
    opportunities: List[OpportunitySignal],
):

    import pandas as pd

    if not opportunities:
        return pd.DataFrame()

    return pd.DataFrame(
        [o.to_dict() for o in opportunities]
    )