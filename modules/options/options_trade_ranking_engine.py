"""
Sprint 4 Phase 5 — Institutional Trade Ranking Engine.
"""
from __future__ import annotations

from typing import Any
import pandas as pd


def _score_candidate(
    candidate: dict[str, Any],
    intelligence_report: dict[str, Any] | None = None,
    flow_report: dict[str, Any] | None = None,
    market_maker_report: dict[str, Any] | None = None,
    volatility_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    score = 50.0
    reasons: list[str] = []

    liquidity = float(candidate.get("liquidity_score") or 0)
    score += min(20, liquidity * 0.20)
    reasons.append(f"Liquidity {liquidity:.1f}/100")

    inst_score = float((intelligence_report or {}).get("institutional_score", 0) or 0)
    if inst_score:
        score += min(15, inst_score * 0.15)
        reasons.append(f"Options intelligence score {inst_score:.1f}")

    flow_score = float((flow_report or {}).get("regime_score", 0) or 0)
    if flow_score:
        score += min(12, flow_score * 0.12)
        reasons.append(f"Flow regime score {flow_score:.1f}")

    mm_score = float((market_maker_report or {}).get("pressure_score", 0) or 0)
    if mm_score:
        # High MM pressure is useful but can increase risk. Moderate boost.
        score += min(8, mm_score * 0.08)
        reasons.append(f"Market maker pressure {mm_score:.1f}")

    vol_regime = (volatility_report or {}).get("volatility_regime")
    strategy = str(candidate.get("strategy") or "")
    if vol_regime in {"ELEVATED_VOL", "EXTREME_VOL", "EVENT_VOL"} and strategy in {"Iron Condor", "Short Premium Basket", "Credit Spread"}:
        score += 10
        reasons.append("Strategy aligns with elevated volatility")
    if vol_regime == "LOW_VOL" and strategy in {"Bull Call Spread", "Bear Put Spread", "Long Volatility Basket", "Debit Spread"}:
        score += 8
        reasons.append("Strategy aligns with low volatility")

    estimated_cost = candidate.get("estimated_cost")
    try:
        if estimated_cost is not None and float(estimated_cost) <= 0:
            score -= 10
            reasons.append("Invalid or zero trade price")
    except Exception:
        pass

    score = round(max(0, min(100, score)), 2)

    if score >= 85:
        grade = "A"
    elif score >= 75:
        grade = "B"
    elif score >= 65:
        grade = "C"
    elif score >= 50:
        grade = "WATCH"
    else:
        grade = "LOW"

    enriched = dict(candidate)
    enriched["rank_score"] = score
    enriched["grade"] = grade
    enriched["score_reasons"] = reasons
    return enriched


def rank_trade_candidates(
    candidates: list[dict[str, Any]],
    intelligence_report: dict[str, Any] | None = None,
    flow_report: dict[str, Any] | None = None,
    market_maker_report: dict[str, Any] | None = None,
    volatility_report: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    ranked = [
        _score_candidate(
            c,
            intelligence_report=intelligence_report,
            flow_report=flow_report,
            market_maker_report=market_maker_report,
            volatility_report=volatility_report,
        )
        for c in candidates or []
    ]
    return sorted(ranked, key=lambda r: r.get("rank_score", 0), reverse=True)


def ranked_candidates_frame(candidates: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for c in candidates or []:
        rows.append({
            "Grade": c.get("grade"),
            "Score": c.get("rank_score"),
            "Strategy": c.get("strategy"),
            "Direction": c.get("direction"),
            "Expiry": c.get("expiry"),
            "Strike": c.get("primary_strike"),
            "Liquidity": c.get("liquidity_score"),
            "Cost": c.get("estimated_cost"),
            "Rationale": c.get("rationale"),
        })
    return pd.DataFrame(rows)
