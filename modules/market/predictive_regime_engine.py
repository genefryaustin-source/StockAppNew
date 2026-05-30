"""
modules/market/predictive_regime_engine.py

Predictive autonomous market cognition engine.

This module forecasts:
- future market regimes
- volatility expansion
- liquidity stress
- panic probabilities
- sentiment fractures
- downside acceleration
- macro instability

Phase 1:
- predictive regime forecasting
- transition probability modeling
- stress anticipation
- volatility forecasting

Future:
- AI macro anticipation
- crash forecasting
- liquidity cascade prediction
- systemic contagion detection
- autonomous defensive preparation
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Dict, List, Any, Optional
import math

from modules.market.regime_detection_engine import (
    MarketRegimeState,
)


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
# FORECAST MODEL
# ---------------------------------------------------

@dataclass
class PredictiveRegimeForecast:

    predicted_regime: str

    forecast_confidence: float

    forecast_horizon: str

    volatility_forecast: float

    stress_forecast: float

    liquidity_forecast: float

    sentiment_forecast: float

    risk_forecast: float

    transition_probability: float

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

            "predicted_regime":
                self.predicted_regime,

            "forecast_confidence":
                round(
                    self.forecast_confidence,
                    4,
                ),

            "forecast_horizon":
                self.forecast_horizon,

            "volatility_forecast":
                round(
                    self.volatility_forecast,
                    4,
                ),

            "stress_forecast":
                round(
                    self.stress_forecast,
                    4,
                ),

            "liquidity_forecast":
                round(
                    self.liquidity_forecast,
                    4,
                ),

            "sentiment_forecast":
                round(
                    self.sentiment_forecast,
                    4,
                ),

            "risk_forecast":
                round(
                    self.risk_forecast,
                    4,
                ),

            "transition_probability":
                round(
                    self.transition_probability,
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
# FORECAST ENGINE
# ---------------------------------------------------

def forecast_market_regime(

    current_state: MarketRegimeState,

    volatility_trend: float = 0.0,

    breadth_trend: float = 0.0,

    sentiment_trend: float = 0.0,

    liquidity_trend: float = 0.0,

    momentum_trend: float = 0.0,

    forecast_horizon: str = "2-4 weeks",

) -> PredictiveRegimeForecast:

    warnings = []

    signals = []

    # -----------------------------------
    # BASE VALUES
    # -----------------------------------

    current_stress = _safe_float(
        current_state.stress_score,
        50.0,
    )

    current_confidence = _safe_float(
        current_state.confidence,
        50.0,
    )

    volatility_forecast = (
        current_stress
        + (
            _safe_float(
                volatility_trend
            ) * 0.60
        )
    )

    stress_forecast = (
        current_stress
        + (
            _safe_float(
                volatility_trend
            ) * 0.30
        )
        - (
            _safe_float(
                breadth_trend
            ) * 0.20
        )
        - (
            _safe_float(
                sentiment_trend
            ) * 0.20
        )
        + (
            _safe_float(
                liquidity_trend
            ) * 0.20
        )
    )

    liquidity_forecast = (
        _safe_float(
            liquidity_trend,
            25.0,
        ) * 1.20
    )

    sentiment_forecast = (
        50.0
        + (
            _safe_float(
                sentiment_trend
            ) * 0.75
        )
    )

    risk_forecast = (
        stress_forecast * 0.65
    ) + (
        volatility_forecast * 0.35
    )

    volatility_forecast = _clamp(
        volatility_forecast
    )

    stress_forecast = _clamp(
        stress_forecast
    )

    liquidity_forecast = _clamp(
        liquidity_forecast
    )

    sentiment_forecast = _clamp(
        sentiment_forecast
    )

    risk_forecast = _clamp(
        risk_forecast
    )

    # -----------------------------------
    # TRANSITION PROBABILITY
    # -----------------------------------

    transition_probability = (
        abs(
            stress_forecast
            - current_stress
        ) * 1.25
    )

    transition_probability = _clamp(
        transition_probability
    )

    # -----------------------------------
    # REGIME FORECAST
    # -----------------------------------

    predicted_regime = (
        current_state.regime
    )

    forecast_confidence = (
        current_confidence
    )

    if (
        stress_forecast >= 75
        or volatility_forecast >= 75
    ):

        predicted_regime = "panic"

        forecast_confidence = 88.0

        warnings.extend([

            "volatility shock risk rising",

            "panic probability increasing",

            "systemic stress escalation",
        ])

    elif (
        sentiment_forecast >= 65
        and breadth_trend > 0
        and momentum_trend > 0
    ):

        predicted_regime = "bull"

        forecast_confidence = 82.0

        signals.extend([

            "positive momentum continuation",

            "constructive sentiment acceleration",

            "broadening participation",
        ])

    elif (
        sentiment_forecast <= 40
        and breadth_trend < 0
    ):

        predicted_regime = "bear"

        forecast_confidence = 80.0

        warnings.extend([

            "negative breadth deterioration",

            "risk-off behavior expanding",
        ])

    elif (
        momentum_trend > 0
        and sentiment_forecast >= 60
    ):

        predicted_regime = (
            "momentum_volatility"
        )

        forecast_confidence = 75.0

        signals.extend([

            "momentum expansion forecast",

            "trend persistence expected",
        ])

    # -----------------------------------
    # EXTRA SIGNALS
    # -----------------------------------

    if volatility_trend > 15:

        warnings.append(
            "volatility acceleration detected"
        )

    if liquidity_trend > 15:

        warnings.append(
            "liquidity conditions deteriorating"
        )

    if breadth_trend < -15:

        warnings.append(
            "market breadth collapsing"
        )

    if sentiment_trend > 15:

        signals.append(
            "sentiment recovery underway"
        )

    if momentum_trend > 15:

        signals.append(
            "momentum strengthening"
        )

    # -----------------------------------
    # OUTPUT
    # -----------------------------------

    return PredictiveRegimeForecast(

        predicted_regime=
            predicted_regime,

        forecast_confidence=
            round(
                forecast_confidence,
                4,
            ),

        forecast_horizon=
            forecast_horizon,

        volatility_forecast=
            volatility_forecast,

        stress_forecast=
            stress_forecast,

        liquidity_forecast=
            liquidity_forecast,

        sentiment_forecast=
            sentiment_forecast,

        risk_forecast=
            risk_forecast,

        transition_probability=
            transition_probability,

        warnings=
            warnings,

        signals=
            signals,

        metadata={

            "current_regime":
                current_state.regime,

            "current_stress":
                current_stress,

            "volatility_trend":
                volatility_trend,

            "breadth_trend":
                breadth_trend,

            "sentiment_trend":
                sentiment_trend,

            "liquidity_trend":
                liquidity_trend,

            "momentum_trend":
                momentum_trend,
        },
    )


# ---------------------------------------------------
# FORECAST DETERIORATION
# ---------------------------------------------------

def detect_forecast_deterioration(
    forecast: PredictiveRegimeForecast,
) -> Dict[str, Any]:

    deterioration_score = 0.0

    warnings = []

    if (
        forecast.predicted_regime
        == "panic"
    ):

        deterioration_score += 40

        warnings.append(
            "panic regime forecast"
        )

    if (
        forecast.volatility_forecast
        >= 70
    ):

        deterioration_score += 20

        warnings.append(
            "extreme volatility forecast"
        )

    if (
        forecast.stress_forecast
        >= 70
    ):

        deterioration_score += 20

        warnings.append(
            "systemic stress rising"
        )

    if (
        forecast.liquidity_forecast
        >= 65
    ):

        deterioration_score += 10

        warnings.append(
            "liquidity fragility forecast"
        )

    if (
        forecast.sentiment_forecast
        <= 35
    ):

        deterioration_score += 10

        warnings.append(
            "sentiment collapse risk"
        )

    deterioration_score = _clamp(
        deterioration_score
    )

    severity = "controlled"

    if deterioration_score >= 75:

        severity = "critical"

    elif deterioration_score >= 55:

        severity = "high"

    elif deterioration_score >= 35:

        severity = "moderate"

    return {

        "deterioration_score":
            round(
                deterioration_score,
                4,
            ),

        "severity":
            severity,

        "warnings":
            warnings,

        "recommended_action":
            (
                "increase defensive posture"
                if deterioration_score >= 55
                else "monitor regime conditions"
            ),
    }