"""
modules/reinforcement/reinforcement_learning_engine.py

Reinforcement investment intelligence engine.

Learns from:
- realized alpha
- prediction accuracy
- execution quality
- regime adaptation
- defensive effectiveness
- opportunity precision
- thesis persistence

Phase 1:
- reward scoring
- factor adaptation
- execution outcome learning
- adaptation directives
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


# ---------------------------------------------------
# DATA MODEL
# ---------------------------------------------------

@dataclass
class ReinforcementLearningState:
    strategy_name: str

    learning_cycle: int

    alpha_accuracy: float
    prediction_accuracy: float
    execution_efficiency: float
    regime_adaptation: float
    defense_effectiveness: float
    opportunity_precision: float

    reward_score: float
    penalty_score: float
    adaptation_strength: float

    factor_adjustments: Dict[str, float] = field(default_factory=dict)

    warnings: List[str] = field(default_factory=list)
    signals: List[str] = field(default_factory=list)

    metadata: Dict[str, Any] = field(default_factory=dict)

    updated_at: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_name": self.strategy_name,
            "learning_cycle": self.learning_cycle,
            "alpha_accuracy": round(self.alpha_accuracy, 4),
            "prediction_accuracy": round(self.prediction_accuracy, 4),
            "execution_efficiency": round(self.execution_efficiency, 4),
            "regime_adaptation": round(self.regime_adaptation, 4),
            "defense_effectiveness": round(self.defense_effectiveness, 4),
            "opportunity_precision": round(self.opportunity_precision, 4),
            "reward_score": round(self.reward_score, 4),
            "penalty_score": round(self.penalty_score, 4),
            "adaptation_strength": round(self.adaptation_strength, 4),
            "factor_adjustments": self.factor_adjustments,
            "warnings": self.warnings,
            "signals": self.signals,
            "metadata": self.metadata,
            "updated_at": self.updated_at,
        }


# ---------------------------------------------------
# REWARD SIGNAL
# ---------------------------------------------------

def compute_reward_signal(
    realized_alpha: float = 0.0,
    prediction_success: bool = False,
    execution_quality: float = 50.0,
    regime_aligned: bool = True,
    defense_preserved_capital: bool = False,
    opportunity_captured: bool = False,
    drawdown: float = 0.0,
    thesis_broken: bool = False,
) -> Dict[str, Any]:

    realized_alpha = _safe_float(realized_alpha)
    execution_quality = _safe_float(execution_quality, 50.0)
    drawdown = abs(_safe_float(drawdown))

    reward = 0.0
    penalty = 0.0

    signals = []
    warnings = []

    # Rewards
    if realized_alpha > 0:
        reward += min(realized_alpha * 2.5, 35.0)
        signals.append("positive realized alpha")

    if prediction_success:
        reward += 18.0
        signals.append("prediction succeeded")

    if execution_quality >= 75:
        reward += 15.0
        signals.append("strong execution quality")

    if regime_aligned:
        reward += 12.0
        signals.append("regime alignment successful")

    if defense_preserved_capital:
        reward += 15.0
        signals.append("defensive posture preserved capital")

    if opportunity_captured:
        reward += 18.0
        signals.append("opportunity captured")

    # Penalties
    if realized_alpha < 0:
        penalty += min(abs(realized_alpha) * 2.5, 35.0)
        warnings.append("negative realized alpha")

    if not prediction_success:
        penalty += 12.0
        warnings.append("prediction failed")

    if execution_quality < 45:
        penalty += 12.0
        warnings.append("weak execution quality")

    if not regime_aligned:
        penalty += 15.0
        warnings.append("regime misalignment")

    if drawdown >= 15:
        penalty += min(drawdown, 30.0)
        warnings.append("excessive drawdown")

    if thesis_broken:
        penalty += 20.0
        warnings.append("investment thesis broke")

    net_reward = _clamp(
        50.0 + reward - penalty,
        0.0,
        100.0,
    )

    return {
        "reward_score": round(reward, 4),
        "penalty_score": round(penalty, 4),
        "net_reward": round(net_reward, 4),
        "signals": signals,
        "warnings": warnings,
    }


# ---------------------------------------------------
# FACTOR WEIGHT UPDATES
# ---------------------------------------------------

def update_factor_weights(
    current_weights: Optional[Dict[str, float]] = None,
    reward_signal: Optional[Dict[str, Any]] = None,
    realized_alpha: float = 0.0,
    market_regime: str = "neutral",
) -> Dict[str, float]:

    weights = dict(current_weights or {
        "quality": 0.10,
        "growth": 0.08,
        "value": 0.07,
        "momentum": 0.10,
        "risk": 0.08,
        "sentiment": 0.07,
        "earnings_nlp": 0.07,
        "confidence": 0.05,
        "macro": 0.06,
        "defense": 0.06,
    })

    net_reward = _safe_float(
        (reward_signal or {}).get("net_reward"),
        50.0,
    )

    alpha = _safe_float(realized_alpha)

    adjustment = (net_reward - 50.0) / 1000.0

    if alpha > 0:
        weights["momentum"] = weights.get("momentum", 0.0) + adjustment
        weights["confidence"] = weights.get("confidence", 0.0) + adjustment
        weights["sentiment"] = weights.get("sentiment", 0.0) + adjustment * 0.5

    else:
        weights["risk"] = weights.get("risk", 0.0) + abs(adjustment)
        weights["quality"] = weights.get("quality", 0.0) + abs(adjustment)
        weights["momentum"] = weights.get("momentum", 0.0) - abs(adjustment) * 0.5

    if market_regime in {"bear", "panic"}:
        weights["defense"] = weights.get("defense", 0.0) + 0.01
        weights["risk"] = weights.get("risk", 0.0) + 0.01
        weights["growth"] = weights.get("growth", 0.0) - 0.005

    if market_regime in {"bull", "momentum_volatility"}:
        weights["growth"] = weights.get("growth", 0.0) + 0.005
        weights["momentum"] = weights.get("momentum", 0.0) + 0.005

    # Clamp safely
    for key in list(weights.keys()):
        weights[key] = round(max(0.0, min(0.25, weights[key])), 4)

    return weights


# ---------------------------------------------------
# EXECUTION OUTCOME LEARNING
# ---------------------------------------------------

def learn_from_execution_outcomes(
    execution_records: List[Dict[str, Any]],
) -> Dict[str, Any]:

    if not execution_records:
        return {
            "execution_efficiency": 50.0,
            "best_execution_style": "unknown",
            "warnings": ["No execution records available."],
            "signals": [],
        }

    quality_scores = []
    style_scores: Dict[str, List[float]] = {}

    warnings = []
    signals = []

    for r in execution_records:
        quality = _safe_float(
            r.get("execution_quality"),
            50.0,
        )

        style = str(
            r.get("entry_style", "unknown")
        )

        alpha = _safe_float(
            r.get("realized_alpha"),
            0.0,
        )

        score = quality + alpha

        quality_scores.append(score)

        style_scores.setdefault(style, []).append(score)

    execution_efficiency = sum(quality_scores) / len(quality_scores)

    best_style = "unknown"
    best_score = -9999.0

    for style, scores in style_scores.items():
        avg = sum(scores) / len(scores)

        if avg > best_score:
            best_style = style
            best_score = avg

    if execution_efficiency >= 70:
        signals.append("execution process adding value")
    elif execution_efficiency < 45:
        warnings.append("execution process underperforming")

    return {
        "execution_efficiency": round(_clamp(execution_efficiency), 4),
        "best_execution_style": best_style,
        "style_scores": {
            k: round(sum(v) / len(v), 4)
            for k, v in style_scores.items()
        },
        "warnings": warnings,
        "signals": signals,
    }


# ---------------------------------------------------
# ADAPTATION DIRECTIVES
# ---------------------------------------------------

def generate_adaptation_directives(
    learning_state: ReinforcementLearningState,
) -> List[str]:

    directives = []

    if learning_state.reward_score > learning_state.penalty_score:
        directives.append("Reinforce current strategy architecture")

    if learning_state.alpha_accuracy < 45:
        directives.append("Reduce weak alpha factor exposure")

    if learning_state.prediction_accuracy < 45:
        directives.append("Lower confidence weighting until prediction accuracy improves")

    if learning_state.execution_efficiency < 50:
        directives.append("Slow deployment pace and improve execution filtering")

    if learning_state.regime_adaptation < 50:
        directives.append("Increase macro and regime sensitivity")

    if learning_state.defense_effectiveness < 50:
        directives.append("Strengthen defensive posture triggers")

    if learning_state.opportunity_precision < 50:
        directives.append("Tighten opportunity detection thresholds")

    if not directives:
        directives.append("Maintain current adaptive configuration")

    return directives


# ---------------------------------------------------
# MAIN LEARNING CYCLE
# ---------------------------------------------------

def run_reinforcement_learning_cycle(
    strategy_name: str,
    learning_cycle: int = 1,
    realized_alpha: float = 0.0,
    prediction_success: bool = False,
    execution_quality: float = 50.0,
    regime_aligned: bool = True,
    defense_preserved_capital: bool = False,
    opportunity_captured: bool = False,
    drawdown: float = 0.0,
    thesis_broken: bool = False,
    current_weights: Optional[Dict[str, float]] = None,
    market_regime: str = "neutral",
) -> ReinforcementLearningState:

    reward = compute_reward_signal(
        realized_alpha=realized_alpha,
        prediction_success=prediction_success,
        execution_quality=execution_quality,
        regime_aligned=regime_aligned,
        defense_preserved_capital=defense_preserved_capital,
        opportunity_captured=opportunity_captured,
        drawdown=drawdown,
        thesis_broken=thesis_broken,
    )

    updated_weights = update_factor_weights(
        current_weights=current_weights,
        reward_signal=reward,
        realized_alpha=realized_alpha,
        market_regime=market_regime,
    )

    alpha_accuracy = _clamp(50.0 + realized_alpha)
    prediction_accuracy = 75.0 if prediction_success else 35.0
    regime_adaptation = 75.0 if regime_aligned else 35.0
    defense_effectiveness = 75.0 if defense_preserved_capital else 50.0
    opportunity_precision = 75.0 if opportunity_captured else 45.0

    adaptation_strength = abs(
        reward["reward_score"] - reward["penalty_score"]
    )

    state = ReinforcementLearningState(
        strategy_name=strategy_name,
        learning_cycle=learning_cycle,
        alpha_accuracy=alpha_accuracy,
        prediction_accuracy=prediction_accuracy,
        execution_efficiency=execution_quality,
        regime_adaptation=regime_adaptation,
        defense_effectiveness=defense_effectiveness,
        opportunity_precision=opportunity_precision,
        reward_score=reward["reward_score"],
        penalty_score=reward["penalty_score"],
        adaptation_strength=round(adaptation_strength, 4),
        factor_adjustments=updated_weights,
        warnings=reward["warnings"],
        signals=reward["signals"],
        metadata={
            "net_reward": reward["net_reward"],
            "market_regime": market_regime,
            "realized_alpha": realized_alpha,
            "drawdown": drawdown,
            "thesis_broken": thesis_broken,
        },
    )

    return state