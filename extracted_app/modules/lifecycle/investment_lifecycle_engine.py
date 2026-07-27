"""
modules/lifecycle/investment_lifecycle_engine.py

Autonomous investment lifecycle intelligence engine.

Tracks:
- thesis evolution
- conviction drift
- execution quality
- realized outcomes
- alpha persistence
- regime alignment
- post-trade intelligence

Phase 1:
- lifecycle tracking
- thesis deterioration detection
- execution outcome analysis
- lifecycle action generation

Future:
- reinforcement learning loops
- adaptive strategy evolution
- AI alpha learning
- autonomous factor evolution
- recursive investment cognition
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
    low: float = -100.0,
    high: float = 100.0,
) -> float:

    return max(
        low,
        min(high, value),
    )


# ---------------------------------------------------
# INVESTMENT LIFECYCLE STATE
# ---------------------------------------------------

@dataclass
class InvestmentLifecycleState:

    symbol: str

    lifecycle_stage: str

    entry_date: Optional[datetime]

    entry_price: float

    current_price: float

    thesis_strength: float

    conviction_drift: float

    realized_return: float

    unrealized_return: float

    risk_drift: float

    execution_quality: float

    alpha_capture: float

    regime_alignment: float

    warnings: List[str] = field(
        default_factory=list
    )

    signals: List[str] = field(
        default_factory=list
    )

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    updated_at: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )

    def total_return(
        self,
    ) -> float:

        return round(
            self.realized_return
            + self.unrealized_return,
            4,
        )

    def to_dict(
        self,
    ) -> Dict[str, Any]:

        return {

            "symbol":
                self.symbol,

            "lifecycle_stage":
                self.lifecycle_stage,

            "entry_date":
                self.entry_date,

            "entry_price":
                round(
                    self.entry_price,
                    4,
                ),

            "current_price":
                round(
                    self.current_price,
                    4,
                ),

            "thesis_strength":
                round(
                    self.thesis_strength,
                    4,
                ),

            "conviction_drift":
                round(
                    self.conviction_drift,
                    4,
                ),

            "realized_return":
                round(
                    self.realized_return,
                    4,
                ),

            "unrealized_return":
                round(
                    self.unrealized_return,
                    4,
                ),

            "risk_drift":
                round(
                    self.risk_drift,
                    4,
                ),

            "execution_quality":
                round(
                    self.execution_quality,
                    4,
                ),

            "alpha_capture":
                round(
                    self.alpha_capture,
                    4,
                ),

            "regime_alignment":
                round(
                    self.regime_alignment,
                    4,
                ),

            "warnings":
                self.warnings,

            "signals":
                self.signals,

            "metadata":
                self.metadata,

            "updated_at":
                self.updated_at,
        }


# ---------------------------------------------------
# THESIS DETERIORATION
# ---------------------------------------------------

def detect_thesis_deterioration(

    ai_confidence: float = 50.0,

    sentiment_score: float = 0.0,

    momentum: float = 50.0,

    volatility: float = 25.0,

    regime_alignment: float = 50.0,

) -> Dict[str, Any]:

    ai_confidence = _safe_float(
        ai_confidence,
        50.0,
    )

    sentiment_score = _safe_float(
        sentiment_score,
        0.0,
    )

    momentum = _safe_float(
        momentum,
        50.0,
    )

    volatility = _safe_float(
        volatility,
        25.0,
    )

    regime_alignment = _safe_float(
        regime_alignment,
        50.0,
    )

    deterioration = 0.0

    warnings = []

    if ai_confidence < 45:

        deterioration += 25

        warnings.append(
            "AI conviction deteriorating"
        )

    if sentiment_score < -0.15:

        deterioration += 20

        warnings.append(
            "negative sentiment acceleration"
        )

    if momentum < 40:

        deterioration += 20

        warnings.append(
            "momentum weakening"
        )

    if volatility > 65:

        deterioration += 15

        warnings.append(
            "volatility instability increasing"
        )

    if regime_alignment < 40:

        deterioration += 20

        warnings.append(
            "regime no longer supportive"
        )

    deterioration = _clamp(
        deterioration,
        0,
        100,
    )

    severity = "controlled"

    if deterioration >= 75:

        severity = "critical"

    elif deterioration >= 55:

        severity = "high"

    elif deterioration >= 35:

        severity = "moderate"

    return {

        "deterioration_score":
            deterioration,

        "severity":
            severity,

        "warnings":
            warnings,
    }


# ---------------------------------------------------
# EXECUTION OUTCOME ANALYSIS
# ---------------------------------------------------

def execution_outcome_analysis(

    entry_price: float,

    current_price: float,

    benchmark_return: float = 0.0,

    realized_return: float = 0.0,

    execution_slippage: float = 0.0,

) -> Dict[str, Any]:

    entry_price = _safe_float(
        entry_price,
        0.0,
    )

    current_price = _safe_float(
        current_price,
        0.0,
    )

    benchmark_return = _safe_float(
        benchmark_return,
        0.0,
    )

    realized_return = _safe_float(
        realized_return,
        0.0,
    )

    execution_slippage = _safe_float(
        execution_slippage,
        0.0,
    )

    unrealized_return = 0.0

    if entry_price > 0:

        unrealized_return = (
            (
                current_price
                - entry_price
            )
            / entry_price
        ) * 100.0

    total_return = (
        realized_return
        + unrealized_return
    )

    alpha_capture = (
        total_return
        - benchmark_return
    )

    execution_quality = 75.0

    execution_quality -= (
        abs(execution_slippage) * 2.0
    )

    if alpha_capture > 0:

        execution_quality += min(
            alpha_capture,
            15.0,
        )

    execution_quality = _clamp(
        execution_quality,
        0,
        100,
    )

    return {

        "unrealized_return":
            round(
                unrealized_return,
                4,
            ),

        "total_return":
            round(
                total_return,
                4,
            ),

        "alpha_capture":
            round(
                alpha_capture,
                4,
            ),

        "execution_quality":
            round(
                execution_quality,
                4,
            ),
    }


# ---------------------------------------------------
# TRACK LIFECYCLE
# ---------------------------------------------------

def track_investment_lifecycle(

    symbol: str,

    entry_price: float,

    current_price: float,

    ai_confidence: float = 50.0,

    sentiment_score: float = 0.0,

    momentum: float = 50.0,

    volatility: float = 25.0,

    regime_alignment: float = 50.0,

    benchmark_return: float = 0.0,

    realized_return: float = 0.0,

    execution_slippage: float = 0.0,

    entry_date: Optional[datetime] = None,

) -> InvestmentLifecycleState:

    warnings = []

    signals = []

    deterioration = (
        detect_thesis_deterioration(

            ai_confidence=ai_confidence,

            sentiment_score=sentiment_score,

            momentum=momentum,

            volatility=volatility,

            regime_alignment=regime_alignment,
        )
    )

    warnings.extend(
        deterioration["warnings"]
    )

    outcome = (
        execution_outcome_analysis(

            entry_price=entry_price,

            current_price=current_price,

            benchmark_return=benchmark_return,

            realized_return=realized_return,

            execution_slippage=execution_slippage,
        )
    )

    thesis_strength = _clamp(

        (
            ai_confidence * 0.35
        )
        + (
            max(
                0.0,
                sentiment_score * 100.0,
            ) * 0.15
        )
        + (
            momentum * 0.25
        )
        + (
            regime_alignment * 0.25
        ),

        0,
        100,
    )

    conviction_drift = _clamp(

        ai_confidence
        - deterioration[
            "deterioration_score"
        ],

        -100,
        100,
    )

    risk_drift = _clamp(

        volatility
        + deterioration[
            "deterioration_score"
        ] * 0.35,

        0,
        100,
    )

    # -----------------------------------
    # LIFECYCLE STAGE
    # -----------------------------------

    lifecycle_stage = "Accumulation"

    total_return = outcome[
        "total_return"
    ]

    if total_return >= 25:

        lifecycle_stage = (
            "Mature Winner"
        )

        signals.append(
            "strong alpha persistence"
        )

    elif total_return >= 10:

        lifecycle_stage = (
            "Trend Expansion"
        )

        signals.append(
            "constructive trend continuation"
        )

    elif total_return < -10:

        lifecycle_stage = (
            "Thesis Breakdown"
        )

        warnings.append(
            "position materially underwater"
        )

    if deterioration[
        "severity"
    ] in {
        "high",
        "critical",
    }:

        lifecycle_stage = (
            "Deteriorating"
        )

    return InvestmentLifecycleState(

        symbol=symbol,

        lifecycle_stage=
            lifecycle_stage,

        entry_date=
            entry_date,

        entry_price=
            entry_price,

        current_price=
            current_price,

        thesis_strength=
            thesis_strength,

        conviction_drift=
            conviction_drift,

        realized_return=
            realized_return,

        unrealized_return=
            outcome[
                "unrealized_return"
            ],

        risk_drift=
            risk_drift,

        execution_quality=
            outcome[
                "execution_quality"
            ],

        alpha_capture=
            outcome[
                "alpha_capture"
            ],

        regime_alignment=
            regime_alignment,

        warnings=
            warnings,

        signals=
            signals,

        metadata={

            "benchmark_return":
                benchmark_return,

            "execution_slippage":
                execution_slippage,

            "deterioration":
                deterioration,

            "outcome":
                outcome,
        },
    )


# ---------------------------------------------------
# GENERATE ACTIONS
# ---------------------------------------------------

def generate_lifecycle_actions(
    lifecycle_state: InvestmentLifecycleState,
) -> List[str]:

    actions = []

    if (
        lifecycle_state.lifecycle_stage
        == "Mature Winner"
    ):

        actions.extend([

            "Hold Core Position",

            "Consider locking partial gains",

            "Maintain trailing protection",
        ])

    elif (
        lifecycle_state.lifecycle_stage
        == "Trend Expansion"
    ):

        actions.extend([

            "Scale Further",

            "Monitor conviction continuation",

            "Evaluate tactical add-ons",
        ])

    elif (
        lifecycle_state.lifecycle_stage
        == "Accumulation"
    ):

        actions.extend([

            "Continue staged accumulation",

            "Monitor momentum confirmation",
        ])

    elif (
        lifecycle_state.lifecycle_stage
        == "Deteriorating"
    ):

        actions.extend([

            "Reduce Exposure",

            "Review thesis assumptions",

            "Evaluate defensive rotation",
        ])

    elif (
        lifecycle_state.lifecycle_stage
        == "Thesis Breakdown"
    ):

        actions.extend([

            "Exit Thesis",

            "Preserve capital",

            "Reallocate toward stronger opportunities",
        ])

    if (
        lifecycle_state.execution_quality
        >= 85
    ):

        actions.append(
            "Execution quality elite"
        )

    if (
        lifecycle_state.alpha_capture
        >= 15
    ):

        actions.append(
            "Strong alpha capture achieved"
        )

    return sorted(
        list(set(actions))
    )