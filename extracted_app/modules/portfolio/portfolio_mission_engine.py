"""
modules/portfolio/portfolio_mission_engine.py

AI portfolio mission engine.

Defines strategic portfolio objectives and constraints.

Phase 1:
- PortfolioMission model
- Growth mission
- Defensive mission
- Momentum mission
- High-conviction mission
- Mission-aware candidate selection
- Mission-aware portfolio construction

Future:
- autonomous mission switching
- macro-aware mission selection
- mission backtesting
- portfolio doctrine learning
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Dict, List, Any, Optional
import math

from modules.portfolio.ai_portfolio_orchestrator import (
    AIPortfolioCandidate,
    construct_ai_portfolio,
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


# ---------------------------------------------------
# PORTFOLIO MISSION MODEL
# ---------------------------------------------------

@dataclass
class PortfolioMission:

    mission_name: str

    description: str

    objective: str

    target_return: float = 0.0

    max_volatility: float = 100.0

    max_position_weight: float = 10.0

    sector_limits: Dict[str, float] = field(
        default_factory=dict
    )

    cash_target: float = 5.0

    rebalance_frequency: str = "monthly"

    risk_tolerance: str = "moderate"

    preferred_factors: List[str] = field(
        default_factory=list
    )

    avoided_factors: List[str] = field(
        default_factory=list
    )

    market_regime_bias: List[str] = field(
        default_factory=list
    )

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    created_at: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )

    def to_dict(
        self,
    ) -> Dict[str, Any]:

        return {
            "mission_name":
                self.mission_name,

            "description":
                self.description,

            "objective":
                self.objective,

            "target_return":
                self.target_return,

            "max_volatility":
                self.max_volatility,

            "max_position_weight":
                self.max_position_weight,

            "sector_limits":
                self.sector_limits,

            "cash_target":
                self.cash_target,

            "rebalance_frequency":
                self.rebalance_frequency,

            "risk_tolerance":
                self.risk_tolerance,

            "preferred_factors":
                self.preferred_factors,

            "avoided_factors":
                self.avoided_factors,

            "market_regime_bias":
                self.market_regime_bias,

            "metadata":
                self.metadata,

            "created_at":
                self.created_at,
        }


# ---------------------------------------------------
# PRESET MISSIONS
# ---------------------------------------------------

def growth_mission() -> PortfolioMission:

    return PortfolioMission(

        mission_name="Growth Mission",

        description=(
            "Targets high-upside equities "
            "with strong growth and AI conviction."
        ),

        objective="maximize upside capture",

        target_return=0.18,

        max_volatility=35.0,

        max_position_weight=12.0,

        cash_target=3.0,

        rebalance_frequency="weekly",

        risk_tolerance="aggressive",

        preferred_factors=[
            "growth",
            "momentum",
            "ai_score",
            "consensus_score",
            "news_sentiment",
        ],

        avoided_factors=[
            "high_risk",
            "weak_momentum",
        ],

        market_regime_bias=[
            "bull",
            "momentum_volatility",
        ],

        sector_limits={
            "Technology": 35.0,
            "Communication Services": 25.0,
            "Consumer Cyclical": 25.0,
        },
    )


def defensive_mission() -> PortfolioMission:

    return PortfolioMission(

        mission_name="Defensive Mission",

        description=(
            "Prioritizes quality, "
            "stability, and downside protection."
        ),

        objective="preserve capital",

        target_return=0.08,

        max_volatility=18.0,

        max_position_weight=8.0,

        cash_target=15.0,

        rebalance_frequency="weekly",

        risk_tolerance="conservative",

        preferred_factors=[
            "quality",
            "low_risk",
            "confidence",
        ],

        avoided_factors=[
            "high_volatility",
            "high_risk",
        ],

        market_regime_bias=[
            "bear",
            "panic",
            "range_bound",
        ],

        sector_limits={
            "Healthcare": 30.0,
            "Consumer Defensive": 30.0,
            "Utilities": 25.0,
        },
    )


def momentum_mission() -> PortfolioMission:

    return PortfolioMission(

        mission_name="Momentum Mission",

        description=(
            "Captures trend persistence "
            "and sentiment acceleration."
        ),

        objective="capture trend continuation",

        target_return=0.16,

        max_volatility=40.0,

        max_position_weight=10.0,

        cash_target=5.0,

        rebalance_frequency="daily",

        risk_tolerance="aggressive",

        preferred_factors=[
            "momentum",
            "trend_strength",
            "news_acceleration",
        ],

        avoided_factors=[
            "trend_breakdown",
            "extreme_risk",
        ],

        market_regime_bias=[
            "bull",
            "momentum_volatility",
        ],

        sector_limits={
            "Technology": 35.0,
            "Consumer Cyclical": 30.0,
            "Communication Services": 25.0,
        },
    )


def high_conviction_ai_mission() -> PortfolioMission:

    return PortfolioMission(

        mission_name=(
            "AI High Conviction Mission"
        ),

        description=(
            "Concentrated portfolio of "
            "highest AI-ranked ideas."
        ),

        objective=(
            "maximize AI conviction alpha"
        ),

        target_return=0.20,

        max_volatility=32.0,

        max_position_weight=15.0,

        cash_target=5.0,

        rebalance_frequency="weekly",

        risk_tolerance=(
            "moderate_aggressive"
        ),

        preferred_factors=[
            "ai_score",
            "consensus_score",
            "ai_confidence",
            "agent_consensus",
        ],

        avoided_factors=[
            "low_confidence",
            "high_risk",
        ],

        market_regime_bias=[
            "bull",
            "neutral",
            "range_bound",
        ],

        sector_limits={
            "Technology": 35.0,
            "Healthcare": 25.0,
            "Financial Services": 25.0,
        },
    )


# ---------------------------------------------------
# MISSION REGISTRY
# ---------------------------------------------------

def get_default_missions(
) -> Dict[str, PortfolioMission]:

    missions = [

        growth_mission(),

        defensive_mission(),

        momentum_mission(),

        high_conviction_ai_mission(),
    ]

    return {

        m.mission_name: m

        for m in missions
    }


def get_mission(
    mission_name: str,
) -> Optional[PortfolioMission]:

    missions = (
        get_default_missions()
    )

    return missions.get(
        mission_name
    )


def list_mission_names(
) -> List[str]:

    return list(
        get_default_missions().keys()
    )


# ---------------------------------------------------
# MISSION-AWARE CANDIDATE SELECTION
# ---------------------------------------------------

def select_mission_candidates(

    candidates,

    mission: PortfolioMission,

    max_candidates: int = 50,

):

    if not candidates:
        return []

    scored = []

    for c in candidates:

        score = 0.0

        score += (
            getattr(
                c,
                "ai_score",
                50.0,
            ) * 0.30
        )

        score += (
            getattr(
                c,
                "consensus_score",
                50.0,
            ) * 0.20
        )

        score += (
            getattr(
                c,
                "confidence",
                50.0,
            ) * 0.15
        )

        preferred = set(

            x.lower()

            for x in (
                mission.preferred_factors
                or []
            )
        )

        avoided = set(

            x.lower()

            for x in (
                mission.avoided_factors
                or []
            )
        )

        # -----------------------------------
        # GROWTH
        # -----------------------------------

        if "growth" in preferred:

            score += (
                getattr(
                    c,
                    "expected_return",
                    0.0,
                ) * 100.0
            ) * 0.15

        # -----------------------------------
        # MOMENTUM
        # -----------------------------------

        if "momentum" in preferred:

            momentum = getattr(
                c,
                "metadata",
                {},
            ).get(
                "momentum",
                50.0,
            )

            score += (
                momentum * 0.12
            )

        # -----------------------------------
        # QUALITY
        # -----------------------------------

        if "quality" in preferred:

            quality = getattr(
                c,
                "metadata",
                {},
            ).get(
                "quality",
                50.0,
            )

            score += (
                quality * 0.12
            )

        # -----------------------------------
        # LOW RISK
        # -----------------------------------

        if (
            "low_risk"
            in preferred
        ):

            score += (
                (
                    100.0
                    - getattr(
                        c,
                        "risk_score",
                        50.0,
                    )
                ) * 0.15
            )

        # -----------------------------------
        # VOLATILITY PENALTY
        # -----------------------------------

        if (
            "high_volatility"
            in avoided
        ):

            score -= (
                getattr(
                    c,
                    "volatility",
                    25.0,
                ) * 0.20
            )

        # -----------------------------------
        # HIGH RISK PENALTY
        # -----------------------------------

        if (
            "high_risk"
            in avoided
        ):

            score -= (
                getattr(
                    c,
                    "risk_score",
                    50.0,
                ) * 0.25
            )

        regime = getattr(
            c,
            "metadata",
            {},
        ).get(
            "market_regime",
            "neutral",
        )

        if (
            regime
            in mission.market_regime_bias
        ):

            score *= 1.10

        sector_limits = (
            mission.sector_limits
            or {}
        )

        if (
            c.sector
            and c.sector
            not in sector_limits
        ):

            score *= 0.92

        scored.append(
            (score, c)
        )

    scored = sorted(

        scored,

        key=lambda x: x[0],

        reverse=True,
    )

    selected = [

        c for _, c in scored[
            :max_candidates
        ]
    ]

    return selected


# ---------------------------------------------------
# MISSION-AWARE PORTFOLIO
# ---------------------------------------------------

def construct_mission_portfolio(

    candidates: List[
        AIPortfolioCandidate
    ],

    mission: PortfolioMission,

    max_positions: int = 20,

):

    selected = (
        select_mission_candidates(

            candidates=candidates,

            mission=mission,

            max_candidates=max_positions,
        )
    )

    if not selected:
        return []

    portfolio = (
        construct_ai_portfolio(

            candidates=selected,

            max_positions=max_positions,

            max_position_weight=(
                mission.max_position_weight
            ),

            sector_max_weight=max(

                mission.sector_limits.values()

            ) if mission.sector_limits else 30.0,

            cash_buffer=(
                mission.cash_target
            ),
        )
    )

    # -----------------------------------
    # MISSION RISK FILTER
    # -----------------------------------

    filtered = []

    for c in portfolio:

        if (
            c.volatility
            > mission.max_volatility
        ):

            continue

        filtered.append(c)

    return filtered