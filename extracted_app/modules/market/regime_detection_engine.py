"""
modules/market/regime_detection_engine.py

Autonomous market regime detection engine.

This module provides:
- market regime classification
- stress detection
- volatility state analysis
- breadth analysis
- liquidity analysis
- risk-on / risk-off intelligence
- transition detection

Phase 1:
- regime classification
- transition detection
- market stress scoring

Future:
- predictive crash detection
- liquidity shock forecasting
- macro instability forecasting
- AI forward regime anticipation
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Dict, List, Any, Optional
import math


# ---------------------------------------------------
# HELPERS
# ---------------------------------------------------

def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:

    try:

        if value is None:
            return default

        value = float(value)

        if math.isnan(value):
            return default

        if math.isinf(value):
            return default

        return value

    except Exception:

        return default


def _clamp(
    value: float,
    low: float = 0.0,
    high: float = 100.0,
) -> float:

    return max(
        low,
        min(high, value),
    )


# ---------------------------------------------------
# MARKET REGIME STATE
# ---------------------------------------------------

@dataclass
class MarketRegimeState:

    regime: str

    confidence: float

    volatility_state: str

    breadth_state: str

    liquidity_state: str

    sentiment_state: str

    risk_state: str

    momentum_state: str

    macro_state: str

    stress_score: float

    warnings: List[str] = field(
        default_factory=list
    )

    signals: List[str] = field(
        default_factory=list
    )

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    generated_at: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )

    def to_dict(
        self,
    ) -> Dict[str, Any]:

        return {

            "regime":
                self.regime,

            "confidence":
                round(
                    self.confidence,
                    4,
                ),

            "volatility_state":
                self.volatility_state,

            "breadth_state":
                self.breadth_state,

            "liquidity_state":
                self.liquidity_state,

            "sentiment_state":
                self.sentiment_state,

            "risk_state":
                self.risk_state,

            "momentum_state":
                self.momentum_state,

            "macro_state":
                self.macro_state,

            "stress_score":
                round(
                    self.stress_score,
                    4,
                ),

            "warnings":
                self.warnings,

            "signals":
                self.signals,

            "metadata":
                self.metadata,

            "generated_at":
                self.generated_at,
        }


# ---------------------------------------------------
# MARKET STRESS SCORE
# ---------------------------------------------------

def market_stress_score(

    volatility: float = 25.0,

    breadth: float = 50.0,

    sentiment: float = 50.0,

    drawdown: float = 0.0,

    liquidity_risk: float = 25.0,

    downside_momentum: float = 25.0,

) -> float:

    volatility = _safe_float(
        volatility,
        25.0,
    )

    breadth = _safe_float(
        breadth,
        50.0,
    )

    sentiment = _safe_float(
        sentiment,
        50.0,
    )

    drawdown = abs(
        _safe_float(
            drawdown,
            0.0,
        )
    )

    liquidity_risk = _safe_float(
        liquidity_risk,
        25.0,
    )

    downside_momentum = _safe_float(
        downside_momentum,
        25.0,
    )

    stress = (
        (volatility * 0.30)
        + ((100.0 - breadth) * 0.20)
        + ((100.0 - sentiment) * 0.15)
        + (drawdown * 0.15)
        + (liquidity_risk * 0.10)
        + (downside_momentum * 0.10)
    )

    return round(
        _clamp(stress),
        4,
    )


# ---------------------------------------------------
# VOLATILITY CLASSIFICATION
# ---------------------------------------------------

def classify_volatility_state(
    volatility: float,
) -> str:

    volatility = _safe_float(
        volatility,
        25.0,
    )

    if volatility >= 70:
        return "crisis"

    if volatility >= 50:
        return "elevated"

    if volatility >= 30:
        return "moderate"

    return "controlled"


# ---------------------------------------------------
# BREADTH CLASSIFICATION
# ---------------------------------------------------

def classify_breadth_state(
    breadth: float,
) -> str:

    breadth = _safe_float(
        breadth,
        50.0,
    )

    if breadth >= 75:
        return "broad_participation"

    if breadth >= 55:
        return "constructive"

    if breadth >= 40:
        return "mixed"

    return "deteriorating"


# ---------------------------------------------------
# SENTIMENT CLASSIFICATION
# ---------------------------------------------------

def classify_sentiment_state(
    sentiment: float,
) -> str:

    sentiment = _safe_float(
        sentiment,
        50.0,
    )

    if sentiment >= 75:
        return "euphoric"

    if sentiment >= 60:
        return "bullish"

    if sentiment >= 45:
        return "neutral"

    if sentiment >= 30:
        return "fearful"

    return "panic"


# ---------------------------------------------------
# LIQUIDITY CLASSIFICATION
# ---------------------------------------------------

def classify_liquidity_state(
    liquidity_risk: float,
) -> str:

    liquidity_risk = _safe_float(
        liquidity_risk,
        25.0,
    )

    if liquidity_risk >= 70:
        return "liquidity_stress"

    if liquidity_risk >= 50:
        return "fragile"

    if liquidity_risk >= 30:
        return "stable"

    return "abundant"


# ---------------------------------------------------
# MOMENTUM CLASSIFICATION
# ---------------------------------------------------

def classify_momentum_state(
    trend_strength: float,
    downside_momentum: float,
) -> str:

    trend_strength = _safe_float(
        trend_strength,
        50.0,
    )

    downside_momentum = _safe_float(
        downside_momentum,
        25.0,
    )

    if (
        trend_strength >= 70
        and downside_momentum < 30
    ):

        return "strong_uptrend"

    if downside_momentum >= 70:
        return "downside_acceleration"

    if trend_strength >= 55:
        return "constructive"

    return "fragile"


# ---------------------------------------------------
# DETECT MARKET REGIME
# ---------------------------------------------------

def detect_market_regime(

    volatility: float = 25.0,

    breadth: float = 50.0,

    sentiment: float = 50.0,

    drawdown: float = 0.0,

    liquidity_risk: float = 25.0,

    downside_momentum: float = 25.0,

    trend_strength: float = 50.0,

    ai_confidence: float = 50.0,

) -> MarketRegimeState:

    warnings = []

    signals = []

    stress = market_stress_score(

        volatility=volatility,

        breadth=breadth,

        sentiment=sentiment,

        drawdown=drawdown,

        liquidity_risk=liquidity_risk,

        downside_momentum=downside_momentum,
    )

    volatility_state = (
        classify_volatility_state(
            volatility
        )
    )

    breadth_state = (
        classify_breadth_state(
            breadth
        )
    )

    sentiment_state = (
        classify_sentiment_state(
            sentiment
        )
    )

    liquidity_state = (
        classify_liquidity_state(
            liquidity_risk
        )
    )

    momentum_state = (
        classify_momentum_state(
            trend_strength,
            downside_momentum,
        )
    )

    # -----------------------------------
    # REGIME DETECTION
    # -----------------------------------

    regime = "neutral"

    confidence = 50.0

    if (
        stress >= 75
        or sentiment_state == "panic"
        or volatility_state == "crisis"
    ):

        regime = "panic"

        confidence = 90.0

        warnings.extend([

            "volatility shock detected",

            "market panic conditions",

            "liquidity instability",
        ])

    elif (
        sentiment >= 65
        and breadth >= 65
        and trend_strength >= 65
        and volatility < 40
    ):

        regime = "bull"

        confidence = 85.0

        signals.extend([

            "broad market participation",

            "constructive momentum",

            "bullish sentiment",
        ])

    elif (
        sentiment <= 40
        and breadth <= 40
    ):

        regime = "bear"

        confidence = 80.0

        warnings.extend([

            "negative breadth deterioration",

            "defensive market conditions",
        ])

    elif (
        trend_strength >= 70
        and sentiment >= 60
    ):

        regime = "momentum_volatility"

        confidence = 75.0

        signals.extend([

            "momentum expansion",

            "trend persistence",
        ])

    # -----------------------------------
    # MACRO STATE
    # -----------------------------------

    if stress >= 75:

        macro_state = "unstable"

    elif stress >= 55:

        macro_state = "fragile"

    elif stress >= 35:

        macro_state = "constructive"

    else:

        macro_state = "stable"

    # -----------------------------------
    # RISK STATE
    # -----------------------------------

    if stress >= 75:

        risk_state = "extreme"

    elif stress >= 60:

        risk_state = "high"

    elif stress >= 40:

        risk_state = "moderate"

    else:

        risk_state = "controlled"

    return MarketRegimeState(

        regime=regime,

        confidence=round(
            confidence,
            4,
        ),

        volatility_state=
            volatility_state,

        breadth_state=
            breadth_state,

        liquidity_state=
            liquidity_state,

        sentiment_state=
            sentiment_state,

        risk_state=
            risk_state,

        momentum_state=
            momentum_state,

        macro_state=
            macro_state,

        stress_score=
            stress,

        warnings=
            warnings,

        signals=
            signals,

        metadata={

            "volatility":
                volatility,

            "breadth":
                breadth,

            "sentiment":
                sentiment,

            "drawdown":
                drawdown,

            "liquidity_risk":
                liquidity_risk,

            "downside_momentum":
                downside_momentum,

            "trend_strength":
                trend_strength,

            "ai_confidence":
                ai_confidence,
        },
    )


# ---------------------------------------------------
# REGIME TRANSITION DETECTION
# ---------------------------------------------------

def detect_regime_transition(

    previous_state:
        Optional[MarketRegimeState],

    current_state:
        MarketRegimeState,

) -> Dict[str, Any]:

    if previous_state is None:

        return {

            "transition_detected":
                False,

            "transition":
                None,

            "severity":
                "none",

            "message":
                "No prior regime available.",
        }

    prev_regime = (
        previous_state.regime
    )

    curr_regime = (
        current_state.regime
    )

    if prev_regime == curr_regime:

        return {

            "transition_detected":
                False,

            "transition":
                None,

            "severity":
                "none",

            "message":
                "No regime transition detected.",
        }

    transition = (
        f"{prev_regime} → {curr_regime}"
    )

    severity = "moderate"

    if (
        curr_regime == "panic"
        or prev_regime == "bull"
        and curr_regime == "bear"
    ):

        severity = "high"

    if (
        prev_regime == "panic"
        and curr_regime == "bull"
    ):

        severity = "high"

    return {

        "transition_detected":
            True,

        "transition":
            transition,

        "severity":
            severity,

        "message":
            f"Market regime transitioned "
            f"from {prev_regime} "
            f"to {curr_regime}.",
    }