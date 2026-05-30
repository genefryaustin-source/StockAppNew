"""
modules/simulation/market_simulation_engine.py

Autonomous financial simulation intelligence engine.

Generates synthetic market futures and tests:
- strategies
- missions
- execution plans
- defense systems
- portfolio doctrines

Phase 1:
- market scenario generation
- strategy performance simulation
- strategy tournaments
- resilient strategy pattern discovery
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


def _avg(values: List[float], default: float = 0.0) -> float:
    clean = [
        _safe_float(v)
        for v in values
        if v is not None
    ]

    if not clean:
        return default

    return sum(clean) / len(clean)


# ---------------------------------------------------
# MARKET SCENARIO MODEL
# ---------------------------------------------------

@dataclass
class SimulatedMarketScenario:
    scenario_name: str
    scenario_type: str
    market_regime: str

    volatility_level: float
    liquidity_state: str
    sentiment_state: str

    drawdown_projection: float
    stress_level: float
    recovery_probability: float

    macro_environment: str

    signals: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    metadata: Dict[str, Any] = field(default_factory=dict)

    generated_at: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_name": self.scenario_name,
            "scenario_type": self.scenario_type,
            "market_regime": self.market_regime,
            "volatility_level": round(self.volatility_level, 4),
            "liquidity_state": self.liquidity_state,
            "sentiment_state": self.sentiment_state,
            "drawdown_projection": round(self.drawdown_projection, 4),
            "stress_level": round(self.stress_level, 4),
            "recovery_probability": round(self.recovery_probability, 4),
            "macro_environment": self.macro_environment,
            "signals": self.signals,
            "warnings": self.warnings,
            "metadata": self.metadata,
            "generated_at": self.generated_at,
        }


# ---------------------------------------------------
# STRATEGY SIM RESULT MODEL
# ---------------------------------------------------

@dataclass
class StrategySimulationResult:
    strategy_name: str
    scenario_name: str

    expected_alpha: float
    expected_drawdown: float
    survival_probability: float
    stress_resilience: float
    recovery_potential: float
    composite_score: float

    recommendation: str

    rationale: str

    warnings: List[str] = field(default_factory=list)
    signals: List[str] = field(default_factory=list)

    metadata: Dict[str, Any] = field(default_factory=dict)

    simulated_at: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_name": self.strategy_name,
            "scenario_name": self.scenario_name,
            "expected_alpha": round(self.expected_alpha, 4),
            "expected_drawdown": round(self.expected_drawdown, 4),
            "survival_probability": round(self.survival_probability, 4),
            "stress_resilience": round(self.stress_resilience, 4),
            "recovery_potential": round(self.recovery_potential, 4),
            "composite_score": round(self.composite_score, 4),
            "recommendation": self.recommendation,
            "rationale": self.rationale,
            "warnings": self.warnings,
            "signals": self.signals,
            "metadata": self.metadata,
            "simulated_at": self.simulated_at,
        }


# ---------------------------------------------------
# SCENARIO GENERATION
# ---------------------------------------------------

def generate_market_scenarios() -> List[SimulatedMarketScenario]:

    return [
        SimulatedMarketScenario(
            scenario_name="AI Bubble Expansion",
            scenario_type="risk_on_expansion",
            market_regime="bull",
            volatility_level=32.0,
            liquidity_state="abundant",
            sentiment_state="euphoric",
            drawdown_projection=8.0,
            stress_level=28.0,
            recovery_probability=78.0,
            macro_environment="growth expansion",
            signals=[
                "AI theme leadership",
                "risk appetite expanding",
                "momentum leadership broadening",
            ],
            warnings=[
                "valuation expansion risk",
                "crowding risk",
            ],
        ),
        SimulatedMarketScenario(
            scenario_name="Liquidity Shock",
            scenario_type="stress_event",
            market_regime="panic",
            volatility_level=82.0,
            liquidity_state="liquidity_stress",
            sentiment_state="panic",
            drawdown_projection=28.0,
            stress_level=88.0,
            recovery_probability=32.0,
            macro_environment="liquidity contraction",
            signals=[],
            warnings=[
                "liquidity evaporating",
                "forced deleveraging risk",
                "spread widening",
            ],
        ),
        SimulatedMarketScenario(
            scenario_name="Panic Cascade",
            scenario_type="crash_environment",
            market_regime="panic",
            volatility_level=92.0,
            liquidity_state="liquidity_stress",
            sentiment_state="panic",
            drawdown_projection=38.0,
            stress_level=96.0,
            recovery_probability=24.0,
            macro_environment="systemic stress",
            warnings=[
                "correlation breakdown",
                "systemic volatility cascade",
                "risk assets under pressure",
            ],
        ),
        SimulatedMarketScenario(
            scenario_name="Soft Landing",
            scenario_type="constructive_macro",
            market_regime="bull",
            volatility_level=24.0,
            liquidity_state="stable",
            sentiment_state="bullish",
            drawdown_projection=6.0,
            stress_level=22.0,
            recovery_probability=82.0,
            macro_environment="stable disinflation",
            signals=[
                "macro stability",
                "earnings resilience",
                "broad participation",
            ],
        ),
        SimulatedMarketScenario(
            scenario_name="Deflation Shock",
            scenario_type="macro_shock",
            market_regime="bear",
            volatility_level=70.0,
            liquidity_state="fragile",
            sentiment_state="fearful",
            drawdown_projection=24.0,
            stress_level=78.0,
            recovery_probability=38.0,
            macro_environment="deflationary stress",
            warnings=[
                "demand contraction",
                "earnings compression",
                "risk-off rotation",
            ],
        ),
        SimulatedMarketScenario(
            scenario_name="Momentum Melt-Up",
            scenario_type="momentum_expansion",
            market_regime="momentum_volatility",
            volatility_level=46.0,
            liquidity_state="stable",
            sentiment_state="euphoric",
            drawdown_projection=12.0,
            stress_level=40.0,
            recovery_probability=72.0,
            macro_environment="momentum expansion",
            signals=[
                "trend acceleration",
                "sentiment acceleration",
                "speculative appetite",
            ],
            warnings=[
                "sharp reversal risk",
            ],
        ),
        SimulatedMarketScenario(
            scenario_name="Credit Stress Event",
            scenario_type="financial_stress",
            market_regime="bear",
            volatility_level=76.0,
            liquidity_state="fragile",
            sentiment_state="fearful",
            drawdown_projection=30.0,
            stress_level=84.0,
            recovery_probability=34.0,
            macro_environment="credit tightening",
            warnings=[
                "credit stress",
                "financial conditions tightening",
                "cyclical exposure vulnerable",
            ],
        ),
        SimulatedMarketScenario(
            scenario_name="Post-Panic Recovery",
            scenario_type="recovery_environment",
            market_regime="momentum_volatility",
            volatility_level=52.0,
            liquidity_state="stable",
            sentiment_state="neutral",
            drawdown_projection=10.0,
            stress_level=44.0,
            recovery_probability=76.0,
            macro_environment="recovery after capitulation",
            signals=[
                "volatility compression",
                "risk appetite rebuilding",
                "oversold recovery",
            ],
            warnings=[
                "false recovery risk",
            ],
        ),
    ]


# ---------------------------------------------------
# STRATEGY PERFORMANCE SIMULATION
# ---------------------------------------------------

def simulate_strategy_performance(
    strategy: Any,
    scenario: SimulatedMarketScenario,
) -> StrategySimulationResult:

    strategy_name = str(
        getattr(
            strategy,
            "strategy_name",
            getattr(strategy, "mission_name", "Unknown Strategy"),
        )
    )

    strategy_type = str(
        getattr(
            strategy,
            "strategy_type",
            getattr(strategy, "objective", "hybrid"),
        )
    ).lower()

    factor_signature = getattr(
        strategy,
        "factor_signature",
        {},
    ) or {}

    confidence = _safe_float(
        getattr(strategy, "confidence", 60.0),
        60.0,
    )

    alpha_capture = _safe_float(
        getattr(strategy, "alpha_capture", 0.0),
        0.0,
    )

    stability_score = _safe_float(
        getattr(strategy, "stability_score", 50.0),
        50.0,
    )

    risk_profile = _safe_float(
        getattr(strategy, "risk_profile", 50.0),
        50.0,
    )

    warnings = []
    signals = []

    # -----------------------------------
    # BASE ALPHA
    # -----------------------------------

    expected_alpha = alpha_capture

    if "momentum" in strategy_type and scenario.market_regime in {
        "bull",
        "momentum_volatility",
    }:
        expected_alpha += 8.0
        signals.append("momentum strategy aligned with market regime")

    if "defensive" in strategy_type and scenario.market_regime in {
        "bear",
        "panic",
    }:
        expected_alpha += 7.0
        signals.append("defensive strategy aligned with stress regime")

    if "quality" in strategy_type and scenario.stress_level >= 60:
        expected_alpha += 4.0
        signals.append("quality factor favored during stress")

    if "growth" in strategy_type and scenario.market_regime == "bull":
        expected_alpha += 6.0
        signals.append("growth strategy favored in bull regime")

    if scenario.market_regime == "panic" and "momentum" in strategy_type:
        expected_alpha -= 10.0
        warnings.append("momentum vulnerable during panic regime")

    # Factor signature effects
    expected_alpha += _safe_float(factor_signature.get("momentum")) * 20.0
    expected_alpha += _safe_float(factor_signature.get("quality")) * 15.0
    expected_alpha += _safe_float(factor_signature.get("sentiment")) * 12.0
    expected_alpha += _safe_float(factor_signature.get("defense")) * (
        18.0 if scenario.stress_level >= 60 else 8.0
    )

    # -----------------------------------
    # DRAWDOWN
    # -----------------------------------

    expected_drawdown = (
        scenario.drawdown_projection
        * (risk_profile / 100.0)
    )

    expected_drawdown -= (
        stability_score * 0.05
    )

    expected_drawdown = max(
        0.0,
        expected_drawdown,
    )

    # -----------------------------------
    # SURVIVAL
    # -----------------------------------

    survival_probability = (
        100.0
        - expected_drawdown
        - (scenario.stress_level * 0.25)
        + (stability_score * 0.30)
        + (confidence * 0.15)
    )

    survival_probability = _clamp(
        survival_probability
    )

    # -----------------------------------
    # STRESS RESILIENCE
    # -----------------------------------

    stress_resilience = (
        stability_score * 0.45
        + (100.0 - risk_profile) * 0.30
        + survival_probability * 0.25
    )

    stress_resilience = _clamp(
        stress_resilience
    )

    # -----------------------------------
    # RECOVERY POTENTIAL
    # -----------------------------------

    recovery_potential = (
        scenario.recovery_probability * 0.50
        + confidence * 0.25
        + max(expected_alpha, 0.0) * 1.5
    )

    recovery_potential = _clamp(
        recovery_potential
    )

    # -----------------------------------
    # COMPOSITE
    # -----------------------------------

    composite_score = (
        expected_alpha * 1.5
        - expected_drawdown * 0.8
        + survival_probability * 0.30
        + stress_resilience * 0.25
        + recovery_potential * 0.20
    )

    composite_score = _clamp(
        composite_score
    )

    if composite_score >= 75:
        recommendation = "Strong Scenario Fit"
    elif composite_score >= 60:
        recommendation = "Constructive Scenario Fit"
    elif composite_score >= 45:
        recommendation = "Neutral Scenario Fit"
    else:
        recommendation = "Weak Scenario Fit"

    rationale = (
        f"{strategy_name} tested against {scenario.scenario_name}. "
        f"Expected alpha={round(expected_alpha, 2)}, "
        f"expected drawdown={round(expected_drawdown, 2)}, "
        f"survival probability={round(survival_probability, 2)}."
    )

    return StrategySimulationResult(
        strategy_name=strategy_name,
        scenario_name=scenario.scenario_name,
        expected_alpha=round(expected_alpha, 4),
        expected_drawdown=round(expected_drawdown, 4),
        survival_probability=round(survival_probability, 4),
        stress_resilience=round(stress_resilience, 4),
        recovery_potential=round(recovery_potential, 4),
        composite_score=round(composite_score, 4),
        recommendation=recommendation,
        rationale=rationale,
        warnings=warnings,
        signals=signals,
        metadata={
            "scenario_type": scenario.scenario_type,
            "market_regime": scenario.market_regime,
            "strategy_type": strategy_type,
            "factor_signature": factor_signature,
        },
    )


# ---------------------------------------------------
# STRATEGY TOURNAMENT
# ---------------------------------------------------

def run_strategy_tournament(
    strategies: List[Any],
    scenarios: Optional[List[SimulatedMarketScenario]] = None,
) -> List[Dict[str, Any]]:

    if not strategies:
        return []

    scenarios = scenarios or generate_market_scenarios()

    tournament = []

    for strategy in strategies:
        results = []

        for scenario in scenarios:
            results.append(
                simulate_strategy_performance(
                    strategy=strategy,
                    scenario=scenario,
                )
            )

        composite_scores = [
            r.composite_score
            for r in results
        ]

        drawdowns = [
            r.expected_drawdown
            for r in results
        ]

        survivals = [
            r.survival_probability
            for r in results
        ]

        alphas = [
            r.expected_alpha
            for r in results
        ]

        tournament.append(
            {
                "strategy_name": str(
                    getattr(
                        strategy,
                        "strategy_name",
                        getattr(strategy, "mission_name", "Unknown Strategy"),
                    )
                ),
                "avg_composite_score": round(_avg(composite_scores), 4),
                "avg_expected_alpha": round(_avg(alphas), 4),
                "avg_expected_drawdown": round(_avg(drawdowns), 4),
                "avg_survival_probability": round(_avg(survivals), 4),
                "scenario_results": results,
            }
        )

    tournament = sorted(
        tournament,
        key=lambda x: (
            x["avg_composite_score"],
            x["avg_expected_alpha"],
            x["avg_survival_probability"],
        ),
        reverse=True,
    )

    return tournament


# ---------------------------------------------------
# RESILIENT STRATEGY PATTERNS
# ---------------------------------------------------

def discover_resilient_strategy_patterns(
    tournament_results: List[Dict[str, Any]],
    min_survival_probability: float = 65.0,
    max_drawdown: float = 25.0,
) -> List[Dict[str, Any]]:

    resilient = []

    for result in tournament_results:

        if (
            result["avg_survival_probability"] >= min_survival_probability
            and result["avg_expected_drawdown"] <= max_drawdown
        ):

            resilient.append(
                {
                    "strategy_name": result["strategy_name"],
                    "avg_composite_score": result["avg_composite_score"],
                    "avg_expected_alpha": result["avg_expected_alpha"],
                    "avg_expected_drawdown": result["avg_expected_drawdown"],
                    "avg_survival_probability": result["avg_survival_probability"],
                    "pattern": "Cross-scenario resilience",
                }
            )

    return resilient


# ---------------------------------------------------
# DATAFRAME EXPORTS
# ---------------------------------------------------

def scenarios_to_dataframe(
    scenarios: List[SimulatedMarketScenario],
):

    import pandas as pd

    if not scenarios:
        return pd.DataFrame()

    return pd.DataFrame(
        [s.to_dict() for s in scenarios]
    )


def tournament_to_dataframe(
    tournament_results: List[Dict[str, Any]],
):

    import pandas as pd

    if not tournament_results:
        return pd.DataFrame()

    rows = []

    for r in tournament_results:
        rows.append(
            {
                "Strategy": r["strategy_name"],
                "Avg Composite Score": r["avg_composite_score"],
                "Avg Expected Alpha": r["avg_expected_alpha"],
                "Avg Expected Drawdown": r["avg_expected_drawdown"],
                "Avg Survival Probability": r["avg_survival_probability"],
            }
        )

    return pd.DataFrame(rows)