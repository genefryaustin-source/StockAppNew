
"""
Sprint 12 Phase 5 — Institutional Options CIO Dashboard Engine
"""

from __future__ import annotations
from typing import Any
import pandas as pd


def _num(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def build_institutional_cio_report(
    portfolio_optimization_report=None,
    trade_selection_report=None,
    risk_rebalancing_report=None,
    auto_income_report=None,
    volatility_report=None,
    market_maker_report=None,
):

    optimization_score = _num(
        (portfolio_optimization_report or {})
        .get("summary", {})
        .get("objective_score", 0)
    )

    trade_score = _num(
        (trade_selection_report or {})
        .get("summary", {})
        .get("top_trade_score", 0)
    )

    rebalance_score = _num(
        (risk_rebalancing_report or {})
        .get("summary", {})
        .get("rebalance_score", 0)
    )

    income_score = _num(
        (auto_income_report or {})
        .get("summary", {})
        .get("income_score", 0)
    )

    vol_rating = (
        (volatility_report or {})
        .get("score", {})
        .get("rating", "NORMAL")
    )

    mm_rating = (
        (market_maker_report or {})
        .get("score", {})
        .get("rating", "NORMAL")
    )

    cio_score = round(
        (
            optimization_score * 0.30
            + trade_score * 0.25
            + income_score * 0.20
            + (100 - rebalance_score) * 0.25
        ),
        2,
    )

    if cio_score >= 85:
        rating = "INSTITUTIONAL STRONG BUY"
    elif cio_score >= 70:
        rating = "ACCUMULATE"
    elif cio_score >= 55:
        rating = "HOLD"
    else:
        rating = "DEFENSIVE"

    directives = []

    if optimization_score < 70:
        directives.append(
            "Improve portfolio optimization score."
        )

    if trade_score < 70:
        directives.append(
            "Increase trade selection quality."
        )

    if rebalance_score > 60:
        directives.append(
            "Reduce portfolio risk through rebalancing."
        )

    if income_score < 70:
        directives.append(
            "Improve recurring income generation."
        )

    directives.append(
        f"Volatility Regime: {vol_rating}"
    )

    directives.append(
        f"Market Maker Regime: {mm_rating}"
    )

    directive_df = pd.DataFrame({
        "Directive": directives
    })

    return {
        "available": True,
        "summary": {
            "cio_score": cio_score,
            "cio_rating": rating,
            "optimization_score": optimization_score,
            "trade_score": trade_score,
            "income_score": income_score,
            "rebalance_score": rebalance_score,
        },
        "directives": directive_df,
    }


def summarize_cio_dashboard(report):

    if not report.get("available"):
        return "Institutional CIO Dashboard unavailable."

    s = report["summary"]

    return (
        f"CIO Score {s['cio_score']}/100 "
        f"({s['cio_rating']}). "
        f"Optimization {s['optimization_score']}, "
        f"Trade Selection {s['trade_score']}, "
        f"Income {s['income_score']}, "
        f"Rebalancing {s['rebalance_score']}."
    )
