"""
modules/risk/autonomous_defense_engine.py

Autonomous portfolio defense engine.

This module provides:
- defensive posture directives
- cash / hedge recommendations
- exposure reduction logic
- portfolio survival scoring
- stress test primitives

Phase 1:
- DefenseDirective model
- generate_defense_directive()
- portfolio_survival_score()
- stress_test_portfolio()

Future:
- hedge instrument selection
- options overlay intelligence
- liquidity cascade defense
- crash preparation workflows
- autonomous defensive rebalancing
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Any, Dict, List, Optional
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

        if math.isnan(value) or math.isinf(value):
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
# DEFENSE DIRECTIVE MODEL
# ---------------------------------------------------

@dataclass
class DefenseDirective:

    directive_type: str

    severity: str

    recommended_cash: float

    hedge_level: float

    reduce_exposure: float

    target_sectors: List[str] = field(
        default_factory=list
    )

    avoid_sectors: List[str] = field(
        default_factory=list
    )

    rationale: str = ""

    warnings: List[str] = field(
        default_factory=list
    )

    actions: List[str] = field(
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
            "directive_type": self.directive_type,
            "severity": self.severity,
            "recommended_cash": round(self.recommended_cash, 4),
            "hedge_level": round(self.hedge_level, 4),
            "reduce_exposure": round(self.reduce_exposure, 4),
            "target_sectors": self.target_sectors,
            "avoid_sectors": self.avoid_sectors,
            "rationale": self.rationale,
            "warnings": self.warnings,
            "actions": self.actions,
            "metadata": self.metadata,
            "generated_at": self.generated_at,
        }


# ---------------------------------------------------
# SURVIVAL SCORE
# ---------------------------------------------------

def portfolio_survival_score(
    portfolio_risk_summary: Optional[Dict[str, Any]] = None,
) -> float:

    if not portfolio_risk_summary:
        return 50.0

    cash = _safe_float(
        portfolio_risk_summary.get("cash_buffer"),
        5.0,
    )

    portfolio_risk = _safe_float(
        portfolio_risk_summary.get("portfolio_risk_score"),
        50.0,
    )

    volatility = _safe_float(
        portfolio_risk_summary.get("portfolio_volatility"),
        25.0,
    )

    concentration = str(
        portfolio_risk_summary.get(
            "concentration_risk",
            "Moderate",
        )
    )

    conviction = str(
        portfolio_risk_summary.get(
            "conviction_strength",
            "Moderate",
        )
    )

    score = 50.0

    # Cash improves survivability
    score += min(cash, 25.0) * 0.8

    # Risk / volatility reduce survivability
    score -= portfolio_risk * 0.25
    score -= volatility * 0.20

    if concentration == "High":
        score -= 15.0
    elif concentration == "Moderate":
        score -= 7.0
    elif concentration == "Controlled":
        score += 5.0

    if "Elite" in conviction:
        score += 12.0
    elif "High" in conviction:
        score += 8.0
    elif "Constructive" in conviction:
        score += 4.0

    return round(
        _clamp(score),
        4,
    )


# ---------------------------------------------------
# DEFENSE DIRECTIVE
# ---------------------------------------------------

def generate_defense_directive(
    current_regime: str = "neutral",
    predictive_forecast: Optional[Any] = None,
    portfolio_risk_summary: Optional[Dict[str, Any]] = None,
    mission_decision: Optional[Any] = None,
) -> DefenseDirective:

    warnings: List[str] = []
    actions: List[str] = []

    target_sectors: List[str] = []
    avoid_sectors: List[str] = []

    # -----------------------------------
    # DEFAULTS
    # -----------------------------------

    severity = "controlled"
    directive_type = "Normal Defensive Monitoring"
    recommended_cash = 5.0
    hedge_level = 0.0
    reduce_exposure = 0.0

    # -----------------------------------
    # FORECAST INPUTS
    # -----------------------------------

    predicted_regime = getattr(
        predictive_forecast,
        "predicted_regime",
        current_regime,
    )

    stress_forecast = _safe_float(
        getattr(
            predictive_forecast,
            "stress_forecast",
            50.0,
        ),
        50.0,
    )

    volatility_forecast = _safe_float(
        getattr(
            predictive_forecast,
            "volatility_forecast",
            25.0,
        ),
        25.0,
    )

    transition_probability = _safe_float(
        getattr(
            predictive_forecast,
            "transition_probability",
            0.0,
        ),
        0.0,
    )

    forecast_warnings = list(
        getattr(
            predictive_forecast,
            "warnings",
            [],
        )
        or []
    )

    warnings.extend(forecast_warnings)

    # -----------------------------------
    # PORTFOLIO INPUTS
    # -----------------------------------

    survival = portfolio_survival_score(
        portfolio_risk_summary
    )

    portfolio_risk = 50.0
    concentration_risk = "Unknown"

    if portfolio_risk_summary:

        portfolio_risk = _safe_float(
            portfolio_risk_summary.get(
                "portfolio_risk_score",
                50.0,
            ),
            50.0,
        )

        concentration_risk = str(
            portfolio_risk_summary.get(
                "concentration_risk",
                "Unknown",
            )
        )

    # -----------------------------------
    # DEFENSE LOGIC
    # -----------------------------------

    if (
        predicted_regime == "panic"
        or stress_forecast >= 75
        or volatility_forecast >= 75
    ):

        severity = "critical"
        directive_type = "Crisis Defensive Posture"
        recommended_cash = 25.0
        hedge_level = 35.0
        reduce_exposure = 30.0

        target_sectors = [
            "Healthcare",
            "Consumer Defensive",
            "Utilities",
            "Cash",
        ]

        avoid_sectors = [
            "Technology",
            "Consumer Cyclical",
            "Small Caps",
            "High Beta",
        ]

        actions.extend([
            "Increase cash reserves immediately",
            "Reduce high-beta exposure",
            "Trim concentrated positions",
            "Rotate toward defensive sectors",
            "Evaluate hedge overlays",
        ])

        warnings.append(
            "Predictive panic or crisis stress conditions detected"
        )

    elif (
        current_regime in {"bear", "panic"}
        or stress_forecast >= 60
        or portfolio_risk >= 65
    ):

        severity = "high"
        directive_type = "Elevated Defensive Posture"
        recommended_cash = 18.0
        hedge_level = 20.0
        reduce_exposure = 18.0

        target_sectors = [
            "Healthcare",
            "Consumer Defensive",
            "Utilities",
            "Cash",
        ]

        avoid_sectors = [
            "Consumer Cyclical",
            "High Beta",
            "Speculative Growth",
        ]

        actions.extend([
            "Increase defensive allocation",
            "Reduce cyclical exposure",
            "Raise cash buffer",
            "Review high-risk positions",
        ])

    elif (
        stress_forecast >= 45
        or volatility_forecast >= 45
        or transition_probability >= 35
        or concentration_risk == "High"
    ):

        severity = "moderate"
        directive_type = "Moderate Defensive Adjustment"
        recommended_cash = 10.0
        hedge_level = 8.0
        reduce_exposure = 8.0

        target_sectors = [
            "Quality",
            "Low Volatility",
            "Cash",
        ]

        avoid_sectors = [
            "Extreme Volatility",
            "Weak Momentum",
        ]

        actions.extend([
            "Trim excessive concentration",
            "Increase quality exposure",
            "Monitor volatility expansion",
        ])

    else:

        severity = "controlled"
        directive_type = "Normal Defensive Monitoring"
        recommended_cash = 5.0
        hedge_level = 0.0
        reduce_exposure = 0.0

        actions.extend([
            "Maintain normal risk posture",
            "Continue monitoring regime conditions",
        ])

    # -----------------------------------
    # SURVIVAL OVERRIDE
    # -----------------------------------

    if survival < 35:

        severity = "critical"
        directive_type = "Portfolio Survival Alert"

        recommended_cash = max(
            recommended_cash,
            25.0,
        )

        hedge_level = max(
            hedge_level,
            30.0,
        )

        reduce_exposure = max(
            reduce_exposure,
            25.0,
        )

        warnings.append(
            "Portfolio survival score is critically low"
        )

        actions.append(
            "Prioritize capital preservation over alpha generation"
        )

    elif survival < 50:

        recommended_cash = max(
            recommended_cash,
            15.0,
        )

        warnings.append(
            "Portfolio survivability is weakening"
        )

    # -----------------------------------
    # MISSION INPUT
    # -----------------------------------

    selected_mission = getattr(
        mission_decision,
        "selected_mission",
        None,
    )

    if selected_mission == "Defensive Mission":

        recommended_cash = max(
            recommended_cash,
            15.0,
        )

        actions.append(
            "Mission rotation already favors defensive positioning"
        )

    # -----------------------------------
    # RATIONALE
    # -----------------------------------

    rationale = (
        f"Defense directive generated from current regime={current_regime}, "
        f"predicted regime={predicted_regime}, stress forecast={round(stress_forecast, 2)}, "
        f"volatility forecast={round(volatility_forecast, 2)}, transition probability="
        f"{round(transition_probability, 2)}, portfolio risk={round(portfolio_risk, 2)}, "
        f"and survival score={round(survival, 2)}."
    )

    return DefenseDirective(
        directive_type=directive_type,
        severity=severity,
        recommended_cash=recommended_cash,
        hedge_level=hedge_level,
        reduce_exposure=reduce_exposure,
        target_sectors=target_sectors,
        avoid_sectors=avoid_sectors,
        rationale=rationale,
        warnings=sorted(set(warnings)),
        actions=sorted(set(actions)),
        metadata={
            "current_regime": current_regime,
            "predicted_regime": predicted_regime,
            "stress_forecast": stress_forecast,
            "volatility_forecast": volatility_forecast,
            "transition_probability": transition_probability,
            "portfolio_risk": portfolio_risk,
            "survival_score": survival,
            "concentration_risk": concentration_risk,
            "selected_mission": selected_mission,
        },
    )


# ---------------------------------------------------
# STRESS TEST PORTFOLIO
# ---------------------------------------------------

def stress_test_portfolio(
    portfolio_risk_summary: Optional[Dict[str, Any]] = None,
    shock_type: str = "market_crash",
) -> Dict[str, Any]:

    if not portfolio_risk_summary:

        return {
            "shock_type": shock_type,
            "estimated_drawdown": 0.0,
            "severity": "unknown",
            "notes": ["No portfolio risk summary available."],
        }

    portfolio_risk = _safe_float(
        portfolio_risk_summary.get("portfolio_risk_score"),
        50.0,
    )

    volatility = _safe_float(
        portfolio_risk_summary.get("portfolio_volatility"),
        25.0,
    )

    cash = _safe_float(
        portfolio_risk_summary.get("cash_buffer"),
        5.0,
    )

    concentration = str(
        portfolio_risk_summary.get(
            "concentration_risk",
            "Moderate",
        )
    )

    multiplier = 1.0

    if shock_type == "market_crash":
        multiplier = 1.35
    elif shock_type == "volatility_shock":
        multiplier = 1.20
    elif shock_type == "liquidity_shock":
        multiplier = 1.45
    elif shock_type == "sector_collapse":
        multiplier = 1.30
    elif shock_type == "momentum_unwind":
        multiplier = 1.15

    drawdown = (
        (portfolio_risk * 0.35)
        + (volatility * 0.30)
        - (cash * 0.20)
    ) * multiplier

    if concentration == "High":
        drawdown += 8.0
    elif concentration == "Moderate":
        drawdown += 3.0

    estimated_drawdown = round(
        _clamp(drawdown),
        4,
    )

    if estimated_drawdown >= 45:
        severity = "critical"
    elif estimated_drawdown >= 30:
        severity = "high"
    elif estimated_drawdown >= 18:
        severity = "moderate"
    else:
        severity = "controlled"

    return {
        "shock_type": shock_type,
        "estimated_drawdown": estimated_drawdown,
        "severity": severity,
        "notes": [
            f"Portfolio risk score={round(portfolio_risk, 2)}",
            f"Portfolio volatility={round(volatility, 2)}",
            f"Cash buffer={round(cash, 2)}",
            f"Concentration risk={concentration}",
        ],
    }