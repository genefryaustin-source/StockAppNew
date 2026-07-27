"""
modules/runtime/autonomous_portfolio_runtime.py

Sovereign Autonomous Portfolio Runtime

Central orchestration runtime for:
- regime cognition
- mission orchestration
- autonomous defense
- opportunity intelligence
- execution intelligence
- lifecycle cognition
- reinforcement learning
- emergent strategies
- market simulations

This is the continuous autonomous portfolio cognition loop.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Any, Dict, List, Optional
import traceback
import uuid


# ---------------------------------------------------
# IMPORTS
# ---------------------------------------------------

from modules.market.regime_detection_engine import (
    detect_market_regime,
)

from modules.market.predictive_regime_engine import (
    forecast_market_regime,
)

from modules.portfolio.mission_rotation_engine import (
    select_optimal_mission,
)

from modules.risk.autonomous_defense_engine import (
    generate_defense_directive,
)

from modules.opportunity.opportunity_detection_engine import (
    detect_opportunity_signals,
)

from modules.execution.autonomous_execution_engine import (
    generate_execution_plan,
)

from modules.lifecycle.investment_lifecycle_engine import (
    track_investment_lifecycle,
)

from modules.reinforcement.reinforcement_learning_engine import (
    run_reinforcement_learning_cycle,
)

from modules.strategy.emergent_strategy_engine import (
    discover_emergent_strategies,
)

from modules.simulation.market_simulation_engine import (
    generate_market_scenarios,
    run_strategy_tournament,
)


# ---------------------------------------------------
# MEMORY STORE
# ---------------------------------------------------

runtime_memory_store: Dict[str, List[Any]] = {

    "regimes": [],

    "forecasts": [],

    "missions": [],

    "defense": [],

    "opportunities": [],

    "executions": [],

    "lifecycles": [],

    "reinforcement": [],

    "strategies": [],

    "simulations": [],

    "runtime_states": [],
}


# ---------------------------------------------------
# RUNTIME STATE
# ---------------------------------------------------

@dataclass
class AutonomousPortfolioState:

    runtime_id: str

    current_regime: Any

    predicted_regime: Any

    active_mission: Any

    defense_posture: Any

    active_opportunities: List[Any]

    active_execution_plans: List[Any]

    lifecycle_states: List[Any]

    reinforcement_state: Any

    emergent_strategies: List[Any]

    simulation_results: List[Any]

    runtime_health: Dict[str, Any]

    last_update: datetime

    warnings: List[str] = field(
        default_factory=list
    )

    signals: List[str] = field(
        default_factory=list
    )

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(
        self,
    ) -> Dict[str, Any]:

        return {

            "runtime_id":
                self.runtime_id,

            "current_regime":
                getattr(
                    self.current_regime,
                    "to_dict",
                    lambda: self.current_regime,
                )(),

            "predicted_regime":
                getattr(
                    self.predicted_regime,
                    "to_dict",
                    lambda: self.predicted_regime,
                )(),

            "active_mission":
                getattr(
                    self.active_mission,
                    "to_dict",
                    lambda: self.active_mission,
                )(),

            "defense_posture":
                getattr(
                    self.defense_posture,
                    "to_dict",
                    lambda: self.defense_posture,
                )(),

            "active_opportunities":
                [
                    getattr(
                        x,
                        "to_dict",
                        lambda: x,
                    )()
                    for x in self.active_opportunities
                ],

            "active_execution_plans":
                [
                    getattr(
                        x,
                        "to_dict",
                        lambda: x,
                    )()
                    for x in self.active_execution_plans
                ],

            "lifecycle_states":
                [
                    getattr(
                        x,
                        "to_dict",
                        lambda: x,
                    )()
                    for x in self.lifecycle_states
                ],

            "reinforcement_state":
                getattr(
                    self.reinforcement_state,
                    "to_dict",
                    lambda: self.reinforcement_state,
                )(),

            "emergent_strategies":
                [
                    getattr(
                        x,
                        "to_dict",
                        lambda: x,
                    )()
                    for x in self.emergent_strategies
                ],

            "simulation_results":
                self.simulation_results,

            "runtime_health":
                self.runtime_health,

            "last_update":
                self.last_update,

            "warnings":
                self.warnings,

            "signals":
                self.signals,

            "metadata":
                self.metadata,
        }


# ---------------------------------------------------
# HEALTH CHECK
# ---------------------------------------------------

def autonomous_runtime_health_check(
    runtime_state: Optional[
        AutonomousPortfolioState
    ] = None,
) -> Dict[str, Any]:

    warnings = []
    signals = []

    health_score = 100.0

    if runtime_state is None:

        return {

            "health_score": 0.0,

            "status": "offline",

            "warnings": [
                "runtime unavailable"
            ],

            "signals": [],
        }

    # -----------------------------------
    # OPPORTUNITY HEALTH
    # -----------------------------------

    if len(
        runtime_state.active_opportunities
    ) == 0:

        health_score -= 10

        warnings.append(
            "no active opportunities detected"
        )

    else:

        signals.append(
            "opportunity engine active"
        )

    # -----------------------------------
    # EXECUTION HEALTH
    # -----------------------------------

    if len(
        runtime_state.active_execution_plans
    ) == 0:

        health_score -= 10

        warnings.append(
            "execution engine inactive"
        )

    else:

        signals.append(
            "execution engine active"
        )

    # -----------------------------------
    # STRATEGY HEALTH
    # -----------------------------------

    if len(
        runtime_state.emergent_strategies
    ) == 0:

        health_score -= 8

        warnings.append(
            "no emergent strategies detected"
        )

    else:

        signals.append(
            "strategy evolution active"
        )

    # -----------------------------------
    # REINFORCEMENT
    # -----------------------------------

    reinforcement = (
        runtime_state.reinforcement_state
    )

    reward_score = getattr(
        reinforcement,
        "reward_score",
        50.0,
    )

    penalty_score = getattr(
        reinforcement,
        "penalty_score",
        0.0,
    )

    if penalty_score > reward_score:

        health_score -= 15

        warnings.append(
            "reinforcement penalties elevated"
        )

    # -----------------------------------
    # DEFENSE
    # -----------------------------------

    defense = (
        runtime_state.defense_posture
    )

    severity = str(
        getattr(
            defense,
            "severity",
            "controlled",
        )
    )

    if severity in {
        "high",
        "critical",
    }:

        warnings.append(
            "elevated defensive posture"
        )

    status = "healthy"

    if health_score < 45:

        status = "critical"

    elif health_score < 70:

        status = "degraded"

    return {

        "health_score":
            round(
                max(
                    0.0,
                    health_score,
                ),
                4,
            ),

        "status":
            status,

        "warnings":
            warnings,

        "signals":
            signals,
    }


# ---------------------------------------------------
# DIRECTIVES
# ---------------------------------------------------

def generate_runtime_directives(
    runtime_state: AutonomousPortfolioState,
) -> List[str]:

    directives = []

    defense = (
        runtime_state.defense_posture
    )

    severity = str(
        getattr(
            defense,
            "severity",
            "controlled",
        )
    )

    regime = str(
        getattr(
            runtime_state.current_regime,
            "regime",
            "neutral",
        )
    )

    if severity in {
        "high",
        "critical",
    }:

        directives.append(
            "Increase Defensive Readiness"
        )

    if regime in {
        "panic",
        "bear",
    }:

        directives.append(
            "Reduce High Volatility Deployment"
        )

    if regime in {
        "momentum_volatility",
    }:

        directives.append(
            "Favor Momentum Continuation Strategies"
        )

    if len(
        runtime_state.active_opportunities
    ) > 10:

        directives.append(
            "Increase Opportunity Filtering Precision"
        )

    if len(
        runtime_state.emergent_strategies
    ) > 5:

        directives.append(
            "Promote High Performing Emergent Strategies"
        )

    directives.append(
        "Continue Autonomous Cognition Loop"
    )

    return sorted(
        list(set(directives))
    )


# ---------------------------------------------------
# MAIN AUTONOMOUS CYCLE
# ---------------------------------------------------

def run_autonomous_cycle(

    ranked_rows: List[Any],

    sentiment_overlay: Optional[
        Dict[str, float]
    ] = None,

    volatility: float = 35.0,

    breadth: float = 58.0,

    sentiment: float = 62.0,

    drawdown: float = 8.0,

    liquidity_risk: float = 32.0,

    downside_momentum: float = 25.0,

    trend_strength: float = 68.0,

    ai_confidence: float = 72.0,

) -> AutonomousPortfolioState:

    sentiment_overlay = (
        sentiment_overlay or {}
    )

    runtime_id = str(
        uuid.uuid4()
    )

    warnings = []
    signals = []

    try:

        # ===================================================
        # 1 REGIME DETECTION
        # ===================================================

        current_regime = (
            detect_market_regime(

                volatility=volatility,

                breadth=breadth,

                sentiment=sentiment,

                drawdown=drawdown,

                liquidity_risk=liquidity_risk,

                downside_momentum=(
                    downside_momentum
                ),

                trend_strength=(
                    trend_strength
                ),

                ai_confidence=(
                    ai_confidence
                ),
            )
        )

        signals.append(
            "regime detection completed"
        )

        # ===================================================
        # 2 FORECAST
        # ===================================================

        forecast = (
            forecast_market_regime(

                current_state=(
                    current_regime
                ),

                volatility_trend=5.0,

                breadth_trend=3.0,

                sentiment_trend=4.0,

                liquidity_trend=2.0,

                momentum_trend=6.0,
            )
        )

        signals.append(
            "predictive forecasting completed"
        )

        # ===================================================
        # 3 MISSION
        # ===================================================

        mission = (
            select_optimal_mission(

                market_regime=(
                    current_regime.regime
                ),

                volatility=(
                    current_regime.stress_score
                ),

                sentiment=sentiment,

                breadth=breadth,

                ai_confidence=(
                    ai_confidence
                ),

                portfolio_risk=42.0,
            )
        )

        signals.append(
            "mission rotation completed"
        )

        # ===================================================
        # 4 DEFENSE
        # ===================================================

        defense = (
            generate_defense_directive(

                current_regime=(
                    current_regime.regime
                ),

                predictive_forecast=(
                    forecast
                ),

                portfolio_risk_summary={

                    "portfolio_risk_score":
                        42.0,

                    "portfolio_volatility":
                        28.0,

                    "cash_buffer":
                        8.0,

                    "concentration_risk":
                        "Moderate",

                    "conviction_strength":
                        "High",
                },

                mission_decision=(
                    mission
                ),
            )
        )

        signals.append(
            "defense posture generated"
        )

        # ===================================================
        # 5 OPPORTUNITIES
        # ===================================================

        opportunities = (
            detect_opportunity_signals(

                rows=ranked_rows,

                sentiment_overlay=(
                    sentiment_overlay
                ),

                market_regime=(
                    current_regime.regime
                ),

                predictive_forecast=(
                    forecast
                ),

                max_results=15,
            )
        )

        signals.append(
            "opportunity scan completed"
        )

        # ===================================================
        # 6 EXECUTION
        # ===================================================

        execution_plans = []

        for opp in opportunities[:10]:

            execution_plans.append(

                generate_execution_plan(

                    opportunity_signal=opp,

                    defense_directive=(
                        defense
                    ),

                    regime_forecast=(
                        forecast
                    ),

                    volatility_state=(
                        current_regime.volatility_state
                    ),
                )
            )

        signals.append(
            "execution planning completed"
        )

        # ===================================================
        # 7 LIFECYCLE
        # ===================================================

        lifecycle_states = []

        for opp in opportunities[:10]:

            lifecycle_states.append(

                track_investment_lifecycle(

                    symbol=opp.symbol,

                    entry_price=100.0,

                    current_price=112.0,

                    ai_confidence=(
                        opp.confidence
                    ),

                    sentiment_score=0.22,

                    momentum=68.0,

                    volatility=35.0,

                    regime_alignment=72.0,

                    benchmark_return=8.0,

                    realized_return=6.0,
                )
            )

        signals.append(
            "lifecycle tracking completed"
        )

        # ===================================================
        # 8 REINFORCEMENT
        # ===================================================

        reinforcement = (
            run_reinforcement_learning_cycle(

                strategy_name=(
                    "Autonomous Adaptive Alpha"
                ),

                learning_cycle=(
                    len(
                        runtime_memory_store[
                            "runtime_states"
                        ]
                    )
                    + 1
                ),

                realized_alpha=12.0,

                prediction_success=True,

                execution_quality=82.0,

                regime_aligned=True,

                defense_preserved_capital=True,

                opportunity_captured=True,

                drawdown=5.0,

                thesis_broken=False,

                market_regime=(
                    current_regime.regime
                ),
            )
        )

        signals.append(
            "reinforcement learning completed"
        )

        # ===================================================
        # 9 EMERGENT STRATEGIES
        # ===================================================

        emergent_strategies = (
            discover_emergent_strategies(

                reinforcement_states=[
                    reinforcement
                ],

                opportunity_signals=(
                    opportunities
                ),
            )
        )

        signals.append(
            "emergent strategy discovery completed"
        )

        # ===================================================
        # 10 SIMULATION
        # ===================================================

        scenarios = (
            generate_market_scenarios()
        )

        simulation_results = (
            run_strategy_tournament(

                strategies=(
                    emergent_strategies
                ),

                scenarios=scenarios,
            )
        )

        signals.append(
            "simulation tournament completed"
        )

        # ===================================================
        # TEMP STATE
        # ===================================================

        temp_state = (
            AutonomousPortfolioState(

                runtime_id=
                    runtime_id,

                current_regime=
                    current_regime,

                predicted_regime=
                    forecast,

                active_mission=
                    mission,

                defense_posture=
                    defense,

                active_opportunities=
                    opportunities,

                active_execution_plans=
                    execution_plans,

                lifecycle_states=
                    lifecycle_states,

                reinforcement_state=
                    reinforcement,

                emergent_strategies=
                    emergent_strategies,

                simulation_results=
                    simulation_results,

                runtime_health={},

                last_update=
                    datetime.now(
                        UTC
                    ),

                warnings=
                    warnings,

                signals=
                    signals,
            )
        )

        # ===================================================
        # 11 HEALTH CHECK
        # ===================================================

        health = (
            autonomous_runtime_health_check(
                temp_state
            )
        )

        temp_state.runtime_health = (
            health
        )

        # ===================================================
        # 12 MEMORY STORE
        # ===================================================

        runtime_memory_store[
            "regimes"
        ].append(current_regime)

        runtime_memory_store[
            "forecasts"
        ].append(forecast)

        runtime_memory_store[
            "missions"
        ].append(mission)

        runtime_memory_store[
            "defense"
        ].append(defense)

        runtime_memory_store[
            "opportunities"
        ].append(opportunities)

        runtime_memory_store[
            "executions"
        ].append(execution_plans)

        runtime_memory_store[
            "lifecycles"
        ].append(lifecycle_states)

        runtime_memory_store[
            "reinforcement"
        ].append(reinforcement)

        runtime_memory_store[
            "strategies"
        ].append(
            emergent_strategies
        )

        runtime_memory_store[
            "simulations"
        ].append(
            simulation_results
        )

        runtime_memory_store[
            "runtime_states"
        ].append(temp_state)

        signals.append(
            "runtime memory updated"
        )

        return temp_state

    except Exception as e:

        traceback.print_exc()

        warnings.append(str(e))

        return AutonomousPortfolioState(

            runtime_id=
                runtime_id,

            current_regime=
                None,

            predicted_regime=
                None,

            active_mission=
                None,

            defense_posture=
                None,

            active_opportunities=
                [],

            active_execution_plans=
                [],

            lifecycle_states=
                [],

            reinforcement_state=
                None,

            emergent_strategies=
                [],

            simulation_results=
                [],

            runtime_health={

                "health_score":
                    0.0,

                "status":
                    "failed",
            },

            last_update=
                datetime.now(
                    UTC
                ),

            warnings=
                warnings,

            signals=
                signals,
        )