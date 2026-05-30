"""
modules/execution/autonomous_execution_engine.py

Autonomous tactical execution intelligence engine.

This module provides:
- tactical execution planning
- staged entry logic
- adaptive scaling
- execution risk overlays
- autonomous exit strategies

Phase 1:
- ExecutionPlan model
- generate_execution_plan()
- adaptive_position_scaling()
- execution_risk_overlay()
- generate_exit_strategy()

Future:
- smart order routing
- liquidity-aware execution
- intraday AI execution timing
- reinforcement execution learning
- autonomous execution optimization
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
# EXECUTION PLAN
# ---------------------------------------------------

@dataclass
class ExecutionPlan:

    symbol: str

    execution_type: str

    entry_style: str

    target_allocation: float

    initial_allocation: float

    scale_schedule: List[str] = field(
        default_factory=list
    )

    risk_budget: float = 0.0

    volatility_adjustment: float = 1.0

    liquidity_adjustment: float = 1.0

    entry_conditions: List[str] = field(
        default_factory=list
    )

    exit_conditions: List[str] = field(
        default_factory=list
    )

    stop_logic: List[str] = field(
        default_factory=list
    )

    take_profit_logic: List[str] = field(
        default_factory=list
    )

    confidence: float = 50.0

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

            "symbol":
                self.symbol,

            "execution_type":
                self.execution_type,

            "entry_style":
                self.entry_style,

            "target_allocation":
                round(
                    self.target_allocation,
                    4,
                ),

            "initial_allocation":
                round(
                    self.initial_allocation,
                    4,
                ),

            "scale_schedule":
                self.scale_schedule,

            "risk_budget":
                round(
                    self.risk_budget,
                    4,
                ),

            "volatility_adjustment":
                round(
                    self.volatility_adjustment,
                    4,
                ),

            "liquidity_adjustment":
                round(
                    self.liquidity_adjustment,
                    4,
                ),

            "entry_conditions":
                self.entry_conditions,

            "exit_conditions":
                self.exit_conditions,

            "stop_logic":
                self.stop_logic,

            "take_profit_logic":
                self.take_profit_logic,

            "confidence":
                round(
                    self.confidence,
                    4,
                ),

            "rationale":
                self.rationale,

            "warnings":
                self.warnings,

            "actions":
                self.actions,

            "metadata":
                self.metadata,

            "generated_at":
                self.generated_at,
        }


# ---------------------------------------------------
# POSITION SCALING
# ---------------------------------------------------

def adaptive_position_scaling(

    ai_confidence: float = 50.0,

    volatility: float = 25.0,

    liquidity_score: float = 50.0,

    mission_risk_tolerance: str = "moderate",

) -> Dict[str, float]:

    ai_confidence = _safe_float(
        ai_confidence,
        50.0,
    )

    volatility = _safe_float(
        volatility,
        25.0,
    )

    liquidity_score = _safe_float(
        liquidity_score,
        50.0,
    )

    base_scale = 1.0

    # -----------------------------------
    # CONFIDENCE
    # -----------------------------------

    if ai_confidence >= 80:
        base_scale *= 1.35

    elif ai_confidence >= 70:
        base_scale *= 1.15

    elif ai_confidence <= 40:
        base_scale *= 0.65

    # -----------------------------------
    # VOLATILITY
    # -----------------------------------

    if volatility >= 70:
        base_scale *= 0.50

    elif volatility >= 50:
        base_scale *= 0.75

    # -----------------------------------
    # LIQUIDITY
    # -----------------------------------

    if liquidity_score <= 35:
        base_scale *= 0.70

    elif liquidity_score >= 70:
        base_scale *= 1.10

    # -----------------------------------
    # MISSION RISK TOLERANCE
    # -----------------------------------

    risk_tolerance = (
        mission_risk_tolerance.lower()
    )

    if "aggressive" in risk_tolerance:
        base_scale *= 1.15

    elif "conservative" in risk_tolerance:
        base_scale *= 0.80

    return {

        "scaling_factor":
            round(
                base_scale,
                4,
            ),

        "deployment_speed":
            round(
                _clamp(
                    base_scale * 50,
                    10,
                    100,
                ),
                4,
            ),
    }


# ---------------------------------------------------
# EXECUTION RISK OVERLAY
# ---------------------------------------------------

def execution_risk_overlay(

    market_regime: str = "neutral",

    volatility_state: str = "moderate",

    defense_severity: str = "controlled",

) -> Dict[str, Any]:

    overlays = []

    risk_multiplier = 1.0

    if market_regime in {
        "panic",
        "bear",
    }:

        risk_multiplier *= 0.65

        overlays.append(
            "reduce aggressive deployment"
        )

    if volatility_state in {
        "crisis",
        "elevated",
    }:

        risk_multiplier *= 0.75

        overlays.append(
            "apply volatility throttling"
        )

    if defense_severity in {
        "high",
        "critical",
    }:

        risk_multiplier *= 0.60

        overlays.append(
            "increase defensive cash posture"
        )

    return {

        "risk_multiplier":
            round(
                risk_multiplier,
                4,
            ),

        "overlays":
            overlays,
    }


# ---------------------------------------------------
# EXIT STRATEGY
# ---------------------------------------------------

def generate_exit_strategy(

    ai_confidence: float = 50.0,

    volatility: float = 25.0,

    market_regime: str = "neutral",

) -> Dict[str, Any]:

    ai_confidence = _safe_float(
        ai_confidence,
        50.0,
    )

    volatility = _safe_float(
        volatility,
        25.0,
    )

    stop_loss = 8.0

    take_profit = 18.0

    trailing_stop = 6.0

    if volatility >= 60:

        stop_loss = 12.0
        trailing_stop = 9.0

    elif volatility <= 25:

        stop_loss = 6.0
        trailing_stop = 4.0

    if ai_confidence >= 80:

        take_profit = 30.0

    elif ai_confidence <= 45:

        take_profit = 12.0

    exit_conditions = [

        "thesis deterioration",

        "AI conviction collapse",

        "regime transition against position",

        "risk escalation",
    ]

    if market_regime in {
        "panic",
        "bear",
    }:

        exit_conditions.append(
            "macro defensive rotation"
        )

    return {

        "stop_loss_pct":
            round(stop_loss, 4),

        "take_profit_pct":
            round(take_profit, 4),

        "trailing_stop_pct":
            round(trailing_stop, 4),

        "exit_conditions":
            exit_conditions,
    }


# ---------------------------------------------------
# EXECUTION PLAN GENERATION
# ---------------------------------------------------

def generate_execution_plan(

    opportunity_signal: Any,

    portfolio_mission: Optional[Any] = None,

    defense_directive: Optional[Any] = None,

    regime_forecast: Optional[Any] = None,

    volatility_state: str = "moderate",

) -> ExecutionPlan:

    symbol = str(
        getattr(
            opportunity_signal,
            "symbol",
            "UNKNOWN",
        )
    ).upper()

    confidence = _safe_float(
        getattr(
            opportunity_signal,
            "confidence",
            50.0,
        ),
        50.0,
    )

    asymmetry_score = _safe_float(
        getattr(
            opportunity_signal,
            "asymmetry_score",
            50.0,
        ),
        50.0,
    )

    market_regime = str(
        getattr(
            regime_forecast,
            "predicted_regime",
            "neutral",
        )
    )

    defense_severity = str(
        getattr(
            defense_directive,
            "severity",
            "controlled",
        )
    )

    # -----------------------------------
    # TARGET ALLOCATION
    # -----------------------------------

    target_allocation = 5.0

    if asymmetry_score >= 85:
        target_allocation = 12.0

    elif asymmetry_score >= 75:
        target_allocation = 9.0

    elif asymmetry_score >= 65:
        target_allocation = 6.0

    # -----------------------------------
    # SCALING
    # -----------------------------------

    scaling = adaptive_position_scaling(

        ai_confidence=confidence,

        volatility=_safe_float(
            getattr(
                opportunity_signal,
                "signal_strength",
                25.0,
            ),
            25.0,
        ),

        liquidity_score=60.0,

        mission_risk_tolerance=str(
            getattr(
                portfolio_mission,
                "risk_tolerance",
                "moderate",
            )
        ),
    )

    # -----------------------------------
    # RISK OVERLAY
    # -----------------------------------

    risk_overlay = execution_risk_overlay(

        market_regime=market_regime,

        volatility_state=volatility_state,

        defense_severity=defense_severity,
    )

    target_allocation *= risk_overlay[
        "risk_multiplier"
    ]

    target_allocation *= scaling[
        "scaling_factor"
    ]

    target_allocation = round(
        _clamp(
            target_allocation,
            1.0,
            15.0,
        ),
        4,
    )

    initial_allocation = round(
        target_allocation * 0.33,
        4,
    )

    # -----------------------------------
    # ENTRY STYLE
    # -----------------------------------

    if confidence >= 80:

        entry_style = (
            "Aggressive Conviction Entry"
        )

    elif confidence >= 65:

        entry_style = (
            "Staggered Conviction Entry"
        )

    else:

        entry_style = (
            "Measured Tactical Entry"
        )

    # -----------------------------------
    # SCALE SCHEDULE
    # -----------------------------------

    scale_schedule = [

        f"{round(initial_allocation, 2)}% initial position",

        f"{round(initial_allocation, 2)}% on confirmation",

        f"{round(target_allocation - (initial_allocation * 2), 2)}% on continuation",
    ]

    # -----------------------------------
    # EXIT STRATEGY
    # -----------------------------------

    exit_strategy = (
        generate_exit_strategy(

            ai_confidence=confidence,

            volatility=_safe_float(
                getattr(
                    opportunity_signal,
                    "signal_strength",
                    25.0,
                ),
                25.0,
            ),

            market_regime=market_regime,
        )
    )

    # -----------------------------------
    # ENTRY CONDITIONS
    # -----------------------------------

    entry_conditions = [

        "positive momentum confirmation",

        "stable volatility environment",

        "AI conviction maintained",
    ]

    if market_regime == "panic":

        entry_conditions.append(
            "wait for volatility stabilization"
        )

    # -----------------------------------
    # ACTIONS
    # -----------------------------------

    actions = [

        "deploy staged execution",

        "monitor conviction drift",

        "evaluate regime transitions",
    ]

    warnings = []

    if market_regime in {
        "panic",
        "bear",
    }:

        warnings.append(
            "defensive market regime active"
        )

    if defense_severity in {
        "high",
        "critical",
    }:

        warnings.append(
            "defensive overlay suppressing sizing"
        )

    rationale = (

        f"Execution plan generated for {symbol}. "
        f"Confidence={round(confidence, 2)}, "
        f"asymmetry={round(asymmetry_score, 2)}, "
        f"market regime={market_regime}, "
        f"defense severity={defense_severity}."
    )

    return ExecutionPlan(

        symbol=symbol,

        execution_type=(
            "Autonomous Tactical Deployment"
        ),

        entry_style=entry_style,

        target_allocation=
            target_allocation,

        initial_allocation=
            initial_allocation,

        scale_schedule=
            scale_schedule,

        risk_budget=
            round(
                target_allocation * 0.50,
                4,
            ),

        volatility_adjustment=
            risk_overlay[
                "risk_multiplier"
            ],

        liquidity_adjustment=
            scaling[
                "scaling_factor"
            ],

        entry_conditions=
            entry_conditions,

        exit_conditions=
            exit_strategy[
                "exit_conditions"
            ],

        stop_logic=[

            f"Stop loss at "
            f"{exit_strategy['stop_loss_pct']}%",

            f"Trailing stop at "
            f"{exit_strategy['trailing_stop_pct']}%",
        ],

        take_profit_logic=[

            f"Primary take profit at "
            f"{exit_strategy['take_profit_pct']}%",

            "scale out incrementally on strength",
        ],

        confidence=
            confidence,

        rationale=
            rationale,

        warnings=
            warnings,

        actions=
            actions,

        metadata={

            "market_regime":
                market_regime,

            "defense_severity":
                defense_severity,

            "risk_overlay":
                risk_overlay,

            "scaling":
                scaling,

            "asymmetry_score":
                asymmetry_score,
        },
    )