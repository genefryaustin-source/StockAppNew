"""
modules/portfolio/mission_rotation_engine.py

Autonomous portfolio mission rotation engine.

This module dynamically selects the optimal
portfolio mission based on:

- market regime
- volatility
- sentiment
- AI confidence
- portfolio risk
- breadth conditions
- macro instability

Phase 1:
- mission rotation decisions
- adaptive mission selection
- transition recommendations

Future:
- predictive regime forecasting
- autonomous strategic switching
- volatility shock anticipation
- liquidity stress adaptation
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Dict, List, Any, Optional
import math

from modules.portfolio.portfolio_mission_engine import (
    PortfolioMission,
    growth_mission,
    defensive_mission,
    momentum_mission,
    high_conviction_ai_mission,
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
# MISSION ROTATION DECISION
# ---------------------------------------------------

@dataclass
class MissionRotationDecision:

    selected_mission: str

    previous_mission: Optional[str]

    reasoning: str

    market_regime: str

    risk_level: str

    confidence: float

    recommended_cash: float

    recommended_turnover: float

    supporting_signals: List[str] = field(
        default_factory=list
    )

    warnings: List[str] = field(
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

            "selected_mission":
                self.selected_mission,

            "previous_mission":
                self.previous_mission,

            "reasoning":
                self.reasoning,

            "market_regime":
                self.market_regime,

            "risk_level":
                self.risk_level,

            "confidence":
                round(
                    self.confidence,
                    4,
                ),

            "recommended_cash":
                round(
                    self.recommended_cash,
                    4,
                ),

            "recommended_turnover":
                round(
                    self.recommended_turnover,
                    4,
                ),

            "supporting_signals":
                self.supporting_signals,

            "warnings":
                self.warnings,

            "metadata":
                self.metadata,

            "generated_at":
                self.generated_at,
        }


# ---------------------------------------------------
# RISK CLASSIFICATION
# ---------------------------------------------------

def classify_risk_level(
    volatility: float,
    portfolio_risk: float,
    sentiment: float,
) -> str:

    vol = _safe_float(
        volatility,
        25.0,
    )

    risk = _safe_float(
        portfolio_risk,
        50.0,
    )

    sent = _safe_float(
        sentiment,
        50.0,
    )

    composite = (
        (vol * 0.40)
        + (risk * 0.40)
        + ((100.0 - sent) * 0.20)
    )

    if composite >= 75:
        return "Extreme"

    if composite >= 60:
        return "High"

    if composite >= 45:
        return "Moderate"

    return "Controlled"


# ---------------------------------------------------
# MISSION SCORING
# ---------------------------------------------------

def score_growth_mission(
    market_regime: str,
    volatility: float,
    sentiment: float,
    ai_confidence: float,
    breadth: float,
) -> float:

    score = 50.0

    if market_regime in {
        "bull",
        "momentum_volatility",
    }:

        score += 25

    if volatility < 35:
        score += 15

    if sentiment > 60:
        score += 15

    if ai_confidence > 70:
        score += 15

    if breadth > 60:
        score += 10

    return round(
        _clamp(score),
        4,
    )


def score_defensive_mission(
    market_regime: str,
    volatility: float,
    sentiment: float,
    portfolio_risk: float,
) -> float:

    score = 40.0

    if market_regime in {
        "bear",
        "panic",
        "range_bound",
    }:

        score += 30

    if volatility > 45:
        score += 20

    if sentiment < 45:
        score += 15

    if portfolio_risk > 60:
        score += 15

    return round(
        _clamp(score),
        4,
    )


def score_momentum_mission(
    market_regime: str,
    volatility: float,
    breadth: float,
    sentiment: float,
) -> float:

    score = 45.0

    if market_regime in {
        "bull",
        "momentum_volatility",
    }:

        score += 25

    if breadth > 65:
        score += 20

    if sentiment > 60:
        score += 15

    if volatility < 40:
        score += 10

    return round(
        _clamp(score),
        4,
    )


def score_high_conviction_mission(
    ai_confidence: float,
    sentiment: float,
    volatility: float,
) -> float:

    score = 50.0

    if ai_confidence > 75:
        score += 30

    if sentiment > 55:
        score += 15

    if volatility < 45:
        score += 10

    return round(
        _clamp(score),
        4,
    )


# ---------------------------------------------------
# SELECT OPTIMAL MISSION
# ---------------------------------------------------

def select_optimal_mission(

    market_regime: str = "neutral",

    volatility: float = 25.0,

    sentiment: float = 50.0,

    breadth: float = 50.0,

    ai_confidence: float = 50.0,

    portfolio_risk: float = 50.0,

    previous_mission: Optional[str] = None,

) -> MissionRotationDecision:

    volatility = _safe_float(
        volatility,
        25.0,
    )

    sentiment = _safe_float(
        sentiment,
        50.0,
    )

    breadth = _safe_float(
        breadth,
        50.0,
    )

    ai_confidence = _safe_float(
        ai_confidence,
        50.0,
    )

    portfolio_risk = _safe_float(
        portfolio_risk,
        50.0,
    )

    growth_score = score_growth_mission(

        market_regime=market_regime,

        volatility=volatility,

        sentiment=sentiment,

        ai_confidence=ai_confidence,

        breadth=breadth,
    )

    defensive_score = score_defensive_mission(

        market_regime=market_regime,

        volatility=volatility,

        sentiment=sentiment,

        portfolio_risk=portfolio_risk,
    )

    momentum_score = score_momentum_mission(

        market_regime=market_regime,

        volatility=volatility,

        breadth=breadth,

        sentiment=sentiment,
    )

    conviction_score = (
        score_high_conviction_mission(

            ai_confidence=ai_confidence,

            sentiment=sentiment,

            volatility=volatility,
        )
    )

    mission_scores = {

        "Growth Mission":
            growth_score,

        "Defensive Mission":
            defensive_score,

        "Momentum Mission":
            momentum_score,

        "AI High Conviction Mission":
            conviction_score,
    }

    selected_mission = max(

        mission_scores,

        key=mission_scores.get,
    )

    selected_score = mission_scores[
        selected_mission
    ]

    supporting_signals = []

    warnings = []

    # -----------------------------------
    # SIGNALS
    # -----------------------------------

    if market_regime in {
        "bull",
        "momentum_volatility",
    }:

        supporting_signals.append(
            "constructive macro regime"
        )

    if market_regime in {
        "bear",
        "panic",
    }:

        warnings.append(
            "defensive macro regime detected"
        )

    if volatility > 50:

        warnings.append(
            "elevated market volatility"
        )

    if sentiment < 45:

        warnings.append(
            "weak sentiment conditions"
        )

    if breadth > 65:

        supporting_signals.append(
            "strong market breadth"
        )

    if ai_confidence > 75:

        supporting_signals.append(
            "high AI confidence"
        )

    # -----------------------------------
    # RECOMMENDED CASH
    # -----------------------------------

    if selected_mission == "Defensive Mission":

        recommended_cash = 15.0

    elif market_regime in {
        "panic",
        "bear",
    }:

        recommended_cash = 18.0

    else:

        recommended_cash = 5.0

    # -----------------------------------
    # TURNOVER
    # -----------------------------------

    if previous_mission:

        if previous_mission != selected_mission:

            recommended_turnover = 35.0

        else:

            recommended_turnover = 10.0

    else:

        recommended_turnover = 20.0

    # -----------------------------------
    # CONFIDENCE
    # -----------------------------------

    confidence = round(
        _clamp(
            selected_score
        ),
        4,
    )

    # -----------------------------------
    # RISK LEVEL
    # -----------------------------------

    risk_level = classify_risk_level(

        volatility=volatility,

        portfolio_risk=portfolio_risk,

        sentiment=sentiment,
    )

    # -----------------------------------
    # REASONING
    # -----------------------------------

    reasoning = (

        f"Selected {selected_mission} "
        f"based on market regime={market_regime}, "
        f"volatility={round(volatility, 2)}, "
        f"sentiment={round(sentiment, 2)}, "
        f"breadth={round(breadth, 2)}, "
        f"AI confidence={round(ai_confidence, 2)}, "
        f"and portfolio risk={round(portfolio_risk, 2)}."
    )

    return MissionRotationDecision(

        selected_mission=
            selected_mission,

        previous_mission=
            previous_mission,

        reasoning=
            reasoning,

        market_regime=
            market_regime,

        risk_level=
            risk_level,

        confidence=
            confidence,

        recommended_cash=
            recommended_cash,

        recommended_turnover=
            recommended_turnover,

        supporting_signals=
            supporting_signals,

        warnings=
            warnings,

        metadata={

            "mission_scores":
                mission_scores,

            "growth_score":
                growth_score,

            "defensive_score":
                defensive_score,

            "momentum_score":
                momentum_score,

            "conviction_score":
                conviction_score,
        },
    )


# ---------------------------------------------------
# TRANSITION RECOMMENDATIONS
# ---------------------------------------------------

def mission_transition_recommendations(
    decision: MissionRotationDecision,
) -> List[str]:

    recommendations = []

    previous = (
        decision.previous_mission
        or "None"
    )

    current = (
        decision.selected_mission
    )

    if previous != current:

        recommendations.append(
            f"Rotate from "
            f"{previous} → {current}"
        )

    if decision.recommended_cash >= 15:

        recommendations.append(
            "Increase defensive cash reserves"
        )

    if (
        decision.market_regime
        in {
            "bear",
            "panic",
        }
    ):

        recommendations.append(
            "Reduce cyclical exposure"
        )

        recommendations.append(
            "Increase defensive positioning"
        )

    if (
        decision.market_regime
        in {
            "bull",
            "momentum_volatility",
        }
    ):

        recommendations.append(
            "Favor growth and momentum exposure"
        )

    if (
        decision.risk_level
        in {
            "High",
            "Extreme",
        }
    ):

        recommendations.append(
            "Reduce portfolio concentration risk"
        )

    if (
        decision.confidence >= 80
    ):

        recommendations.append(
            "High-confidence mission environment detected"
        )

    return recommendations


# ---------------------------------------------------
# LOAD MISSION OBJECT
# ---------------------------------------------------

def load_selected_mission(
    mission_name: str,
) -> PortfolioMission:

    mapping = {

        "Growth Mission":
            growth_mission(),

        "Defensive Mission":
            defensive_mission(),

        "Momentum Mission":
            momentum_mission(),

        "AI High Conviction Mission":
            high_conviction_ai_mission(),
    }

    return mapping.get(
        mission_name,
        growth_mission(),
    )