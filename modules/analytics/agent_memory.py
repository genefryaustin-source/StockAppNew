
"""
modules/analytics/agent_memory.py

Long-term memory system for autonomous research agents.

Tracks:
- agent decisions
- realized outcomes
- alpha generation
- regime effectiveness
- confidence calibration
- narrative reliability

Future:
- reinforcement learning
- autonomous weight evolution
- agent trust scoring
- thesis persistence
- portfolio attribution
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from datetime import datetime, UTC
from typing import Any, Dict, List, Optional
import math
import statistics


# ---------------------------------------------------
# DATA MODELS
# ---------------------------------------------------

@dataclass
class AgentMemoryRecord:

    symbol: str

    agent_name: str

    decision_score: float

    confidence: float

    outcome_return: Optional[float] = None

    benchmark_return: Optional[float] = None

    outcome_alpha: Optional[float] = None

    success: Optional[bool] = None

    market_regime: str = "unknown"

    thesis: str = ""

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    timestamp: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )


@dataclass
class AgentReliability:

    agent_name: str

    total_predictions: int

    successful_predictions: int

    failed_predictions: int

    win_rate: float

    avg_alpha: float

    avg_confidence: float

    reliability_score: float

    regime_effectiveness: Dict[str, float]

    updated_at: datetime


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
# MEMORY STORE
# ---------------------------------------------------

class AgentMemoryStore:

    def __init__(self):

        self.records: List[
            AgentMemoryRecord
        ] = []

    # ---------------------------------------------------
    # ADD MEMORY
    # ---------------------------------------------------

    def add_record(
        self,
        record: AgentMemoryRecord,
    ) -> None:

        self.records.append(record)

    # ---------------------------------------------------
    # BULK INSERT
    # ---------------------------------------------------

    def add_records(
        self,
        records: List[
            AgentMemoryRecord
        ],
    ) -> None:

        self.records.extend(records)

    # ---------------------------------------------------
    # ALL RECORDS
    # ---------------------------------------------------

    def get_records(
        self,
        agent_name: Optional[str] = None,
        symbol: Optional[str] = None,
    ) -> List[AgentMemoryRecord]:

        records = self.records

        if agent_name:

            records = [

                r for r in records

                if r.agent_name == agent_name
            ]

        if symbol:

            records = [

                r for r in records

                if r.symbol == symbol
            ]

        return records

    # ---------------------------------------------------
    # UPDATE OUTCOMES
    # ---------------------------------------------------

    def update_outcomes(
        self,
        symbol: str,
        realized_return: float,
        benchmark_return: float = 0.0,
    ) -> None:

        for record in self.records:

            if record.symbol != symbol:
                continue

            rr = _safe_float(
                realized_return
            )

            br = _safe_float(
                benchmark_return
            )

            alpha = rr - br

            record.outcome_return = rr

            record.benchmark_return = br

            record.outcome_alpha = alpha

            record.success = alpha > 0

    # ---------------------------------------------------
    # RELIABILITY
    # ---------------------------------------------------

    def compute_agent_reliability(
        self,
    ) -> Dict[
        str,
        AgentReliability,
    ]:

        grouped = {}

        for record in self.records:

            grouped.setdefault(
                record.agent_name,
                [],
            ).append(record)

        output = {}

        for agent_name, records in grouped.items():

            completed = [

                r for r in records

                if r.outcome_alpha
                is not None
            ]

            if not completed:
                continue

            wins = len([

                r for r in completed

                if r.success

            ])

            losses = len(completed) - wins

            win_rate = (
                wins / len(completed)
            ) if completed else 0.0

            alphas = [

                _safe_float(
                    r.outcome_alpha
                )

                for r in completed
            ]

            confidences = [

                _safe_float(
                    r.confidence
                )

                for r in completed
            ]

            avg_alpha = (
                statistics.mean(alphas)
                if alphas else 0.0
            )

            avg_conf = (
                statistics.mean(confidences)
                if confidences else 0.0
            )

            reliability_score = (
                (
                    win_rate * 50.0
                )
                + (
                    avg_alpha * 100.0
                )
                + (
                    avg_conf * 0.15
                )
            )

            reliability_score = _clamp(
                reliability_score
            )

            regime_stats = {}

            regime_groups = {}

            for r in completed:

                regime_groups.setdefault(
                    r.market_regime,
                    [],
                ).append(r)

            for regime, rs in regime_groups.items():

                regime_wins = len([

                    x for x in rs

                    if x.success

                ])

                regime_stats[regime] = round(

                    regime_wins / len(rs),

                    4,
                )

            output[agent_name] = (

                AgentReliability(

                    agent_name=agent_name,

                    total_predictions=len(
                        completed
                    ),

                    successful_predictions=wins,

                    failed_predictions=losses,

                    win_rate=round(
                        win_rate,
                        4,
                    ),

                    avg_alpha=round(
                        avg_alpha,
                        4,
                    ),

                    avg_confidence=round(
                        avg_conf,
                        4,
                    ),

                    reliability_score=round(
                        reliability_score,
                        4,
                    ),

                    regime_effectiveness=(
                        regime_stats
                    ),

                    updated_at=datetime.now(
                        UTC
                    ),
                )
            )

        return output

    # ---------------------------------------------------
    # AGENT WEIGHTS
    # ---------------------------------------------------

    def compute_agent_weights(
        self,
    ) -> Dict[str, float]:

        reliability = (
            self.compute_agent_reliability()
        )

        if not reliability:
            return {}

        total = sum(

            r.reliability_score

            for r in reliability.values()
        )

        if total <= 0:
            return {}

        weights = {}

        for agent, r in reliability.items():

            weights[agent] = round(

                r.reliability_score
                / total,

                4,
            )

        return weights

    # ---------------------------------------------------
    # REGIME ANALYSIS
    # ---------------------------------------------------

    def regime_summary(
        self,
    ) -> Dict[str, Any]:

        regimes = {}

        for r in self.records:

            if (
                r.market_regime
                not in regimes
            ):

                regimes[
                    r.market_regime
                ] = {
                    "count": 0,
                    "wins": 0,
                    "alphas": [],
                }

            regimes[
                r.market_regime
            ]["count"] += 1

            if r.success:

                regimes[
                    r.market_regime
                ]["wins"] += 1

            if (
                r.outcome_alpha
                is not None
            ):

                regimes[
                    r.market_regime
                ]["alphas"].append(
                    r.outcome_alpha
                )

        output = {}

        for regime, stats in regimes.items():

            count = stats["count"]

            wins = stats["wins"]

            alphas = stats["alphas"]

            output[regime] = {

                "count": count,

                "win_rate": round(
                    wins / count,
                    4,
                ) if count else 0.0,

                "avg_alpha": round(
                    statistics.mean(
                        alphas
                    ),
                    4,
                ) if alphas else 0.0,
            }

        return output

    # ---------------------------------------------------
    # EXPORT
    # ---------------------------------------------------

    def export_records(
        self,
    ) -> List[Dict[str, Any]]:

        return [

            asdict(r)

            for r in self.records
        ]


# ---------------------------------------------------
# GLOBAL MEMORY
# ---------------------------------------------------

_GLOBAL_AGENT_MEMORY = (
    AgentMemoryStore()
)


def get_agent_memory_store(
    reset: bool = False,
) -> AgentMemoryStore:

    global _GLOBAL_AGENT_MEMORY

    if reset:

        _GLOBAL_AGENT_MEMORY = (
            AgentMemoryStore()
        )

    return _GLOBAL_AGENT_MEMORY