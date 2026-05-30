"""
modules/strategy/emergent_strategy_engine.py

Emergent autonomous strategy intelligence engine.

Discovers:
- hidden factor relationships
- recurring alpha archetypes
- regime-specific strategies
- defensive alpha behaviors
- opportunity clusters
- strategy mutations

Phase 1:
- emergent strategy profiles
- strategy discovery
- behavior clustering
- strategy mutation generation
- strategy promotion scoring
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
# DATA MODEL
# ---------------------------------------------------

@dataclass
class EmergentStrategyProfile:
    strategy_name: str
    strategy_type: str
    market_regime: str

    alpha_profile: float
    risk_profile: float

    factor_signature: Dict[str, float] = field(default_factory=dict)

    win_rate: float = 0.0
    alpha_capture: float = 0.0
    adaptation_score: float = 0.0
    novelty_score: float = 0.0
    stability_score: float = 0.0
    confidence: float = 0.0

    warnings: List[str] = field(default_factory=list)
    signals: List[str] = field(default_factory=list)

    metadata: Dict[str, Any] = field(default_factory=dict)

    discovered_at: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_name": self.strategy_name,
            "strategy_type": self.strategy_type,
            "market_regime": self.market_regime,
            "alpha_profile": round(self.alpha_profile, 4),
            "risk_profile": round(self.risk_profile, 4),
            "factor_signature": self.factor_signature,
            "win_rate": round(self.win_rate, 4),
            "alpha_capture": round(self.alpha_capture, 4),
            "adaptation_score": round(self.adaptation_score, 4),
            "novelty_score": round(self.novelty_score, 4),
            "stability_score": round(self.stability_score, 4),
            "confidence": round(self.confidence, 4),
            "warnings": self.warnings,
            "signals": self.signals,
            "metadata": self.metadata,
            "discovered_at": self.discovered_at,
        }


# ---------------------------------------------------
# STRATEGY CLASSIFICATION
# ---------------------------------------------------

def classify_strategy_type(
    factor_signature: Dict[str, float],
    market_regime: str = "neutral",
) -> str:

    momentum = _safe_float(
        factor_signature.get("momentum")
    )

    quality = _safe_float(
        factor_signature.get("quality")
    )

    sentiment = _safe_float(
        factor_signature.get("sentiment")
    )

    defense = _safe_float(
        factor_signature.get("defense")
    )

    risk = _safe_float(
        factor_signature.get("risk")
    )

    growth = _safe_float(
        factor_signature.get("growth")
    )

    value = _safe_float(
        factor_signature.get("value")
    )

    if market_regime in {"panic", "bear"} and defense >= 0.10:
        return "Defensive Alpha"

    if momentum >= 0.10 and sentiment >= 0.07:
        return "Sentiment Momentum"

    if quality >= 0.10 and risk >= 0.09:
        return "Quality Risk-Control"

    if growth >= 0.10 and momentum >= 0.10:
        return "Growth Momentum"

    if value >= 0.09 and quality >= 0.09:
        return "Value Quality"

    return "Hybrid Adaptive"


def _strategy_name(
    strategy_type: str,
    market_regime: str,
) -> str:

    return f"{strategy_type} / {market_regime.title()} Regime"


# ---------------------------------------------------
# STRATEGY DISCOVERY
# ---------------------------------------------------

def discover_emergent_strategies(
    lifecycle_outcomes: Optional[List[Dict[str, Any]]] = None,
    reinforcement_states: Optional[List[Any]] = None,
    execution_outcomes: Optional[List[Dict[str, Any]]] = None,
    opportunity_signals: Optional[List[Any]] = None,
    regime_history: Optional[List[Any]] = None,
    min_confidence: float = 45.0,
) -> List[EmergentStrategyProfile]:

    lifecycle_outcomes = lifecycle_outcomes or []
    reinforcement_states = reinforcement_states or []
    execution_outcomes = execution_outcomes or []
    opportunity_signals = opportunity_signals or []
    regime_history = regime_history or []

    strategy_groups: Dict[str, Dict[str, Any]] = {}

    # -----------------------------------
    # REINFORCEMENT STATES
    # -----------------------------------

    for state in reinforcement_states:

        weights = getattr(
            state,
            "factor_adjustments",
            {},
        ) or {}

        regime = str(
            getattr(
                state,
                "metadata",
                {},
            ).get(
                "market_regime",
                "neutral",
            )
        )

        strategy_type = classify_strategy_type(
            weights,
            market_regime=regime,
        )

        key = f"{strategy_type}:{regime}"

        group = strategy_groups.setdefault(
            key,
            {
                "strategy_type": strategy_type,
                "market_regime": regime,
                "alphas": [],
                "wins": 0,
                "count": 0,
                "weights": [],
                "execution": [],
                "opportunities": [],
                "warnings": [],
                "signals": [],
            },
        )

        alpha = _safe_float(
            getattr(
                state,
                "metadata",
                {},
            ).get(
                "realized_alpha",
                0.0,
            )
        )

        group["alphas"].append(alpha)

        group["count"] += 1

        if alpha > 0:
            group["wins"] += 1

        group["weights"].append(weights)

        group["signals"].extend(
            getattr(state, "signals", []) or []
        )

        group["warnings"].extend(
            getattr(state, "warnings", []) or []
        )

    # -----------------------------------
    # LIFECYCLE OUTCOMES
    # -----------------------------------

    for outcome in lifecycle_outcomes:

        regime = str(
            outcome.get(
                "market_regime",
                "neutral",
            )
        )

        stage = str(
            outcome.get(
                "lifecycle_stage",
                "unknown",
            )
        )

        strategy_type = (
            "Lifecycle Winner"
            if stage in {
                "Mature Winner",
                "Trend Expansion",
            }
            else "Lifecycle Recovery"
        )

        key = f"{strategy_type}:{regime}"

        group = strategy_groups.setdefault(
            key,
            {
                "strategy_type": strategy_type,
                "market_regime": regime,
                "alphas": [],
                "wins": 0,
                "count": 0,
                "weights": [],
                "execution": [],
                "opportunities": [],
                "warnings": [],
                "signals": [],
            },
        )

        alpha = _safe_float(
            outcome.get(
                "alpha_capture",
                0.0,
            )
        )

        group["alphas"].append(alpha)
        group["count"] += 1

        if alpha > 0:
            group["wins"] += 1

        if stage:
            group["signals"].append(stage)

    # -----------------------------------
    # EXECUTION OUTCOMES
    # -----------------------------------

    for record in execution_outcomes:

        style = str(
            record.get(
                "entry_style",
                "Execution Adaptive",
            )
        )

        regime = str(
            record.get(
                "market_regime",
                "neutral",
            )
        )

        key = f"{style}:{regime}"

        group = strategy_groups.setdefault(
            key,
            {
                "strategy_type": style,
                "market_regime": regime,
                "alphas": [],
                "wins": 0,
                "count": 0,
                "weights": [],
                "execution": [],
                "opportunities": [],
                "warnings": [],
                "signals": [],
            },
        )

        alpha = _safe_float(
            record.get(
                "realized_alpha",
                0.0,
            )
        )

        group["alphas"].append(alpha)
        group["count"] += 1
        group["execution"].append(record)

        if alpha > 0:
            group["wins"] += 1

    # -----------------------------------
    # OPPORTUNITY SIGNALS
    # -----------------------------------

    for opp in opportunity_signals:

        opp_type = str(
            getattr(
                opp,
                "opportunity_type",
                "Opportunity Adaptive",
            )
        )

        regime = str(
            getattr(
                opp,
                "market_regime",
                "neutral",
            )
        )

        key = f"{opp_type}:{regime}"

        group = strategy_groups.setdefault(
            key,
            {
                "strategy_type": opp_type,
                "market_regime": regime,
                "alphas": [],
                "wins": 0,
                "count": 0,
                "weights": [],
                "execution": [],
                "opportunities": [],
                "warnings": [],
                "signals": [],
            },
        )

        confidence = _safe_float(
            getattr(opp, "confidence", 50.0)
        )

        asymmetry = _safe_float(
            getattr(opp, "asymmetry_score", 50.0)
        )

        implied_alpha = (
            (confidence + asymmetry) / 2.0
        ) - 50.0

        group["alphas"].append(implied_alpha)
        group["count"] += 1
        group["opportunities"].append(opp)

        if implied_alpha > 0:
            group["wins"] += 1

        group["signals"].extend(
            getattr(opp, "signals", []) or []
        )

        group["warnings"].extend(
            getattr(opp, "warnings", []) or []
        )

    profiles: List[EmergentStrategyProfile] = []

    # -----------------------------------
    # BUILD PROFILES
    # -----------------------------------

    for _, group in strategy_groups.items():

        count = max(1, group["count"])

        win_rate = group["wins"] / count

        alpha_capture = _avg(
            group["alphas"],
            0.0,
        )

        factor_signature = _average_factor_signatures(
            group["weights"]
        )

        if not factor_signature:
            factor_signature = _default_factor_signature(
                group["strategy_type"]
            )

        risk_profile = _estimate_strategy_risk(
            group["strategy_type"],
            group["warnings"],
        )

        novelty_score = _estimate_novelty(
            group["strategy_type"],
            group["market_regime"],
        )

        stability_score = _clamp(
            100.0 - risk_profile
            + (win_rate * 10.0)
        )

        adaptation_score = _clamp(
            (win_rate * 45.0)
            + max(alpha_capture, 0.0) * 2.0
            + stability_score * 0.25
        )

        confidence = _clamp(
            (win_rate * 45.0)
            + max(alpha_capture, 0.0) * 1.5
            + min(count * 5.0, 25.0)
        )

        if confidence < min_confidence:
            continue

        strategy_type = group["strategy_type"]

        regime = group["market_regime"]

        profiles.append(
            EmergentStrategyProfile(
                strategy_name=_strategy_name(
                    strategy_type,
                    regime,
                ),
                strategy_type=strategy_type,
                market_regime=regime,
                alpha_profile=round(alpha_capture, 4),
                risk_profile=round(risk_profile, 4),
                factor_signature=factor_signature,
                win_rate=round(win_rate, 4),
                alpha_capture=round(alpha_capture, 4),
                adaptation_score=round(adaptation_score, 4),
                novelty_score=round(novelty_score, 4),
                stability_score=round(stability_score, 4),
                confidence=round(confidence, 4),
                warnings=sorted(set(group["warnings"])),
                signals=sorted(set(group["signals"])),
                metadata={
                    "sample_count": count,
                    "execution_samples": len(group["execution"]),
                    "opportunity_samples": len(group["opportunities"]),
                },
            )
        )

    profiles = sorted(
        profiles,
        key=lambda x: (
            x.confidence,
            x.alpha_capture,
            x.adaptation_score,
        ),
        reverse=True,
    )

    return profiles


# ---------------------------------------------------
# FACTOR SIGNATURES
# ---------------------------------------------------

def _average_factor_signatures(
    weights_list: List[Dict[str, float]],
) -> Dict[str, float]:

    if not weights_list:
        return {}

    keys = set()

    for weights in weights_list:
        keys.update(weights.keys())

    output = {}

    for key in keys:
        output[key] = round(
            _avg(
                [
                    _safe_float(w.get(key))
                    for w in weights_list
                ],
                0.0,
            ),
            4,
        )

    return output


def _default_factor_signature(
    strategy_type: str,
) -> Dict[str, float]:

    t = strategy_type.lower()

    if "momentum" in t:
        return {
            "momentum": 0.14,
            "sentiment": 0.09,
            "confidence": 0.07,
        }

    if "defensive" in t:
        return {
            "quality": 0.12,
            "risk": 0.12,
            "defense": 0.10,
        }

    if "quality" in t:
        return {
            "quality": 0.12,
            "value": 0.08,
            "risk": 0.08,
        }

    if "recovery" in t:
        return {
            "sentiment": 0.10,
            "momentum": 0.08,
            "risk": 0.08,
        }

    return {
        "quality": 0.08,
        "momentum": 0.08,
        "sentiment": 0.07,
        "confidence": 0.06,
    }


# ---------------------------------------------------
# RISK / NOVELTY ESTIMATES
# ---------------------------------------------------

def _estimate_strategy_risk(
    strategy_type: str,
    warnings: List[str],
) -> float:

    base = 45.0

    t = strategy_type.lower()

    if "momentum" in t:
        base += 10

    if "recovery" in t:
        base += 12

    if "defensive" in t:
        base -= 12

    if "volatility" in t:
        base += 15

    base += min(
        len(warnings) * 3.0,
        20.0,
    )

    return _clamp(base)


def _estimate_novelty(
    strategy_type: str,
    market_regime: str,
) -> float:

    novelty = 50.0

    if "hybrid" in strategy_type.lower():
        novelty += 10

    if "recovery" in strategy_type.lower():
        novelty += 15

    if market_regime in {
        "panic",
        "momentum_volatility",
    }:
        novelty += 10

    return _clamp(novelty)


# ---------------------------------------------------
# CLUSTER STRATEGY BEHAVIORS
# ---------------------------------------------------

def cluster_strategy_behaviors(
    profiles: List[EmergentStrategyProfile],
) -> Dict[str, List[EmergentStrategyProfile]]:

    clusters: Dict[str, List[EmergentStrategyProfile]] = {}

    for profile in profiles:

        key = profile.strategy_type

        clusters.setdefault(
            key,
            [],
        ).append(profile)

    return clusters


# ---------------------------------------------------
# STRATEGY MUTATIONS
# ---------------------------------------------------

def generate_strategy_mutations(
    profile: EmergentStrategyProfile,
) -> List[Dict[str, Any]]:

    mutations = []

    base = profile.factor_signature or {}

    # Momentum boost mutation
    momentum_mutation = dict(base)
    momentum_mutation["momentum"] = round(
        min(
            0.25,
            _safe_float(
                momentum_mutation.get("momentum"),
                0.08,
            )
            + 0.025,
        ),
        4,
    )

    mutations.append(
        {
            "mutation_name": f"{profile.strategy_name} / Momentum Boost",
            "parent_strategy": profile.strategy_name,
            "factor_signature": momentum_mutation,
            "rationale": "Tests whether stronger momentum emphasis improves alpha persistence.",
        }
    )

    # Risk-control mutation
    risk_mutation = dict(base)
    risk_mutation["risk"] = round(
        min(
            0.25,
            _safe_float(
                risk_mutation.get("risk"),
                0.08,
            )
            + 0.025,
        ),
        4,
    )

    mutations.append(
        {
            "mutation_name": f"{profile.strategy_name} / Risk-Control Variant",
            "parent_strategy": profile.strategy_name,
            "factor_signature": risk_mutation,
            "rationale": "Tests whether stronger risk control improves drawdown resilience.",
        }
    )

    # Sentiment mutation
    sentiment_mutation = dict(base)
    sentiment_mutation["sentiment"] = round(
        min(
            0.25,
            _safe_float(
                sentiment_mutation.get("sentiment"),
                0.07,
            )
            + 0.02,
        ),
        4,
    )

    mutations.append(
        {
            "mutation_name": f"{profile.strategy_name} / Sentiment Adaptive Variant",
            "parent_strategy": profile.strategy_name,
            "factor_signature": sentiment_mutation,
            "rationale": "Tests whether sentiment acceleration improves opportunity timing.",
        }
    )

    return mutations


# ---------------------------------------------------
# PROMOTION
# ---------------------------------------------------

def promote_high_performing_strategies(
    profiles: List[EmergentStrategyProfile],
    min_confidence: float = 70.0,
    min_win_rate: float = 0.55,
    min_alpha_capture: float = 3.0,
) -> List[EmergentStrategyProfile]:

    promoted = []

    for profile in profiles:

        if (
            profile.confidence >= min_confidence
            and profile.win_rate >= min_win_rate
            and profile.alpha_capture >= min_alpha_capture
        ):

            promoted.append(profile)

    return sorted(
        promoted,
        key=lambda x: (
            x.confidence,
            x.alpha_capture,
            x.stability_score,
        ),
        reverse=True,
    )


# ---------------------------------------------------
# DATAFRAME EXPORT
# ---------------------------------------------------

def emergent_strategies_to_dataframe(
    profiles: List[EmergentStrategyProfile],
):

    import pandas as pd

    if not profiles:
        return pd.DataFrame()

    return pd.DataFrame(
        [p.to_dict() for p in profiles]
    )