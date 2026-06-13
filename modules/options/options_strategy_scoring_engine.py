"""
modules/options/options_strategy_scoring_engine.py

Phase 5 — Multi-Leg Strategy Command Center scoring engine.
Scores candidate options strategies across probability, risk/reward, theta,
volatility edge, smart-money alignment, dealer alignment, and event edge.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any
import math


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, float) and math.isnan(value):
            return default
        return float(value)
    except Exception:
        return default


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


@dataclass
class StrategyScore:
    strategy_name: str
    category: str
    probability_score: float
    risk_reward_score: float
    expected_value_score: float
    theta_score: float
    vega_score: float
    gamma_score: float
    dealer_alignment_score: float
    smart_money_alignment_score: float
    iv_edge_score: float
    earnings_edge_score: float
    overall_score: float
    grade: str
    label: str
    notes: list[str]


def grade_score(score: float) -> str:
    if score >= 90:
        return "A+"
    if score >= 85:
        return "A"
    if score >= 80:
        return "A-"
    if score >= 75:
        return "B+"
    if score >= 70:
        return "B"
    if score >= 65:
        return "B-"
    if score >= 60:
        return "C+"
    if score >= 55:
        return "C"
    if score >= 50:
        return "C-"
    return "D"


def label_score(score: float) -> str:
    if score >= 85:
        return "High Conviction"
    if score >= 72:
        return "Strong Candidate"
    if score >= 60:
        return "Moderate Candidate"
    if score >= 50:
        return "Watchlist Candidate"
    return "Weak Candidate"


def infer_strategy_category(strategy_name: str) -> str:
    name = strategy_name.lower()
    if any(k in name for k in ["covered call", "cash secured", "wheel", "jade", "income"]):
        return "Income"
    if any(k in name for k in ["straddle", "strangle", "calendar", "diagonal", "volatility"]):
        return "Volatility"
    if any(k in name for k in ["iron condor", "butterfly", "neutral"]):
        return "Neutral"
    if any(k in name for k in ["bear", "put", "synthetic short"]):
        return "Bearish"
    if any(k in name for k in ["bull", "call", "synthetic long", "poor man's"]):
        return "Bullish"
    return "Custom"


def _direction_for_strategy(strategy_name: str) -> str:
    cat = infer_strategy_category(strategy_name)
    if cat == "Bullish":
        return "Bullish"
    if cat == "Bearish":
        return "Bearish"
    if cat in {"Income", "Neutral"}:
        return "Neutral"
    if cat == "Volatility":
        return "Volatile"
    return "Neutral"


def _sentiment_alignment(strategy_direction: str, label: str, score: float | None = None) -> float:
    label = str(label or "Neutral").lower()
    base = 50.0
    if score is not None:
        base = _num(score, 50.0)
    if strategy_direction == "Bullish":
        if "bull" in label:
            return max(base, 75.0)
        if "bear" in label:
            return min(base, 35.0)
    if strategy_direction == "Bearish":
        if "bear" in label:
            return max(100.0 - base if base < 50 else base, 75.0)
        if "bull" in label:
            return min(100.0 - base if base > 50 else base, 35.0)
    if strategy_direction == "Neutral":
        return 80.0 if "neutral" in label else 55.0
    if strategy_direction == "Volatile":
        return 75.0 if any(k in label for k in ["volatile", "high", "expansion"]) else 55.0
    return 50.0


def score_strategy(
    strategy_name: str,
    metrics: dict[str, Any] | None = None,
    smart_money: dict[str, Any] | None = None,
    dealer: dict[str, Any] | None = None,
    volatility: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Score one strategy candidate and return a dict for UI use."""
    metrics = metrics or {}
    smart_money = smart_money or {}
    dealer = dealer or {}
    volatility = volatility or {}

    category = infer_strategy_category(strategy_name)
    direction = _direction_for_strategy(strategy_name)
    notes: list[str] = []

    pop = _num(metrics.get("probability_profit"), _num(metrics.get("pop"), 0.55))
    if pop > 1:
        pop = pop / 100.0
    probability_score = _clamp(pop * 100.0)

    max_profit = _num(metrics.get("max_profit"), 0.0)
    max_loss = abs(_num(metrics.get("max_loss"), 0.0))
    net_credit = _num(metrics.get("net_credit"), -_num(metrics.get("net_debit"), 0.0))
    if max_loss > 0 and max_profit > 0:
        rr = max_profit / max_loss
        risk_reward_score = _clamp(45.0 + min(45.0, rr * 30.0))
    elif net_credit > 0 and max_loss > 0:
        risk_reward_score = _clamp(50.0 + min(35.0, (net_credit / max_loss) * 120.0))
    else:
        risk_reward_score = 55.0

    ev = _num(metrics.get("expected_value"), 0.0)
    capital = max(1.0, _num(metrics.get("capital_required"), max_loss or 1000.0))
    expected_value_score = _clamp(50.0 + (ev / capital) * 250.0)

    theta = _num(metrics.get("theta"), 0.0)
    vega = _num(metrics.get("vega"), 0.0)
    gamma = abs(_num(metrics.get("gamma"), 0.0))

    theta_score = _clamp(55.0 + theta * 120.0 if category in {"Income", "Neutral"} else 55.0 - abs(theta) * 40.0)
    iv_rank = _num(volatility.get("iv_rank"), _num(volatility.get("iv_rank_proxy"), 50.0))
    vol_regime = str(volatility.get("volatility_regime") or volatility.get("regime") or "Normal")

    if category == "Volatility":
        vega_score = _clamp(50.0 + max(0.0, vega) * 80.0 + (iv_rank - 50.0) * 0.15)
    elif category in {"Income", "Neutral"}:
        vega_score = _clamp(70.0 + (iv_rank - 50.0) * 0.35 - max(0.0, vega) * 25.0)
    else:
        vega_score = _clamp(60.0 - abs(vega) * 20.0)

    gamma_score = _clamp(80.0 - gamma * 250.0 if category in {"Income", "Neutral"} else 60.0 - gamma * 75.0)

    sm_sent = smart_money.get("sentiment", {}) if isinstance(smart_money.get("sentiment"), dict) else {}
    sm_label = sm_sent.get("label") or smart_money.get("label") or smart_money.get("bias") or "Neutral"
    sm_score_raw = sm_sent.get("score") if "score" in sm_sent else smart_money.get("score")
    smart_money_alignment_score = _sentiment_alignment(direction, str(sm_label), _num(sm_score_raw, 50.0))

    dealer_state = str(dealer.get("gamma_state") or dealer.get("dealer_bias") or dealer.get("label") or "Neutral")
    dealer_score_raw = dealer.get("score") or dealer.get("dealer_score")
    dealer_alignment_score = _sentiment_alignment(direction, dealer_state, _num(dealer_score_raw, 50.0))

    if category in {"Income", "Neutral"}:
        iv_edge_score = _clamp(50.0 + (iv_rank - 50.0) * 0.75)
    elif category == "Volatility":
        iv_edge_score = _clamp(65.0 if "expansion" in vol_regime.lower() else 50.0 + (55.0 - iv_rank) * 0.35)
    else:
        iv_edge_score = _clamp(55.0 + abs(iv_rank - 50.0) * 0.2)

    earnings_edge = volatility.get("earnings_edge") or volatility.get("event_edge") or {}
    if isinstance(earnings_edge, dict):
        earnings_edge_score = _num(earnings_edge.get("score"), 55.0)
    else:
        earnings_edge_score = _num(earnings_edge, 55.0)

    weights = {
        "probability": 0.16,
        "risk_reward": 0.14,
        "ev": 0.12,
        "theta": 0.10,
        "vega": 0.10,
        "gamma": 0.08,
        "dealer": 0.10,
        "smart_money": 0.10,
        "iv_edge": 0.06,
        "earnings": 0.04,
    }
    overall = (
        probability_score * weights["probability"]
        + risk_reward_score * weights["risk_reward"]
        + expected_value_score * weights["ev"]
        + theta_score * weights["theta"]
        + vega_score * weights["vega"]
        + gamma_score * weights["gamma"]
        + dealer_alignment_score * weights["dealer"]
        + smart_money_alignment_score * weights["smart_money"]
        + iv_edge_score * weights["iv_edge"]
        + earnings_edge_score * weights["earnings"]
    )
    overall = round(_clamp(overall), 1)

    if smart_money_alignment_score >= 70:
        notes.append("Aligned with smart-money directional bias.")
    if dealer_alignment_score >= 70:
        notes.append("Aligned with dealer-positioning backdrop.")
    if iv_edge_score >= 70:
        notes.append("Volatility pricing supports this structure.")
    if probability_score < 50:
        notes.append("Probability of profit is below ideal threshold.")
    if not notes:
        notes.append("Balanced setup; monitor liquidity, spreads, and event risk.")

    result = StrategyScore(
        strategy_name=strategy_name,
        category=category,
        probability_score=round(probability_score, 1),
        risk_reward_score=round(risk_reward_score, 1),
        expected_value_score=round(expected_value_score, 1),
        theta_score=round(theta_score, 1),
        vega_score=round(vega_score, 1),
        gamma_score=round(gamma_score, 1),
        dealer_alignment_score=round(dealer_alignment_score, 1),
        smart_money_alignment_score=round(smart_money_alignment_score, 1),
        iv_edge_score=round(iv_edge_score, 1),
        earnings_edge_score=round(earnings_edge_score, 1),
        overall_score=overall,
        grade=grade_score(overall),
        label=label_score(overall),
        notes=notes,
    )
    return asdict(result)


def score_strategy_list(
    candidates: list[dict[str, Any]],
    smart_money: dict[str, Any] | None = None,
    dealer: dict[str, Any] | None = None,
    volatility: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    scored: list[dict[str, Any]] = []
    for candidate in candidates or []:
        name = str(candidate.get("strategy_name") or candidate.get("strategy") or "Custom Strategy")
        metrics = dict(candidate.get("metrics") or candidate)
        row = dict(candidate)
        row["score"] = score_strategy(name, metrics, smart_money, dealer, volatility)
        row["overall_score"] = row["score"]["overall_score"]
        row["grade"] = row["score"]["grade"]
        row["label"] = row["score"]["label"]
        row["category"] = row["score"]["category"]
        scored.append(row)
    scored.sort(key=lambda r: _num(r.get("overall_score")), reverse=True)
    return scored
