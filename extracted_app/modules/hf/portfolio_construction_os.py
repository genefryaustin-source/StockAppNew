"""
HF-3 Portfolio Construction & Capital Allocation OS.
Converts committee-approved equity ideas into portfolio-ready allocations.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Iterable
import math
import pandas as pd

@dataclass
class PortfolioCandidate:
    symbol: str
    thesis_score: float = 50.0
    conviction_score: float = 50.0
    risk_score: float = 50.0
    valuation_score: float = 50.0
    momentum_score: float = 50.0
    sector: str = "Unknown"
    current_weight: float = 0.0
    target_weight: float = 0.0
    max_weight: float = 0.10
    min_weight: float = 0.0
    notes: str = ""

def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, float) and math.isnan(value):
            return default
        return float(value)
    except Exception:
        return default

def normalize_candidates(candidates: Iterable[dict[str, Any]] | pd.DataFrame) -> list[PortfolioCandidate]:
    if candidates is None:
        return []
    rows = candidates.to_dict("records") if isinstance(candidates, pd.DataFrame) else list(candidates)
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("symbol") or row.get("ticker") or "").upper().strip()
        if not symbol:
            continue
        out.append(PortfolioCandidate(
            symbol=symbol,
            thesis_score=_num(row.get("thesis_score"), _num(row.get("research_score"), 50)),
            conviction_score=_num(row.get("conviction_score"), 50),
            risk_score=_num(row.get("risk_score"), 50),
            valuation_score=_num(row.get("valuation_score"), 50),
            momentum_score=_num(row.get("momentum_score"), 50),
            sector=str(row.get("sector") or "Unknown"),
            current_weight=_num(row.get("current_weight"), 0),
            max_weight=_num(row.get("max_weight"), 0.10),
            min_weight=_num(row.get("min_weight"), 0),
            notes=str(row.get("notes") or ""),
        ))
    return out

def composite_alpha_score(candidate: PortfolioCandidate) -> float:
    quality = (
        candidate.thesis_score * 0.30
        + candidate.conviction_score * 0.25
        + candidate.valuation_score * 0.20
        + candidate.momentum_score * 0.15
    )
    risk_penalty = max(0.0, candidate.risk_score - 50.0) * 0.35
    return round(max(0.0, min(100.0, quality - risk_penalty)), 2)

def _weight_action(delta: float) -> str:
    if delta > 0.02:
        return "Increase"
    if delta < -0.02:
        return "Reduce"
    if abs(delta) <= 0.005:
        return "Hold"
    return "Minor Rebalance"

def construct_portfolio(
    candidates: Iterable[dict[str, Any]] | pd.DataFrame,
    max_positions: int = 25,
    gross_exposure: float = 1.0,
    max_single_name_weight: float = 0.08,
    max_sector_weight: float = 0.30,
) -> dict[str, Any]:
    normalized = normalize_candidates(candidates)
    if not normalized:
        return {"status": "empty", "message": "No candidates provided.", "positions": [], "summary": {}}

    ranked = sorted(normalized, key=composite_alpha_score, reverse=True)[:max(1, int(max_positions))]
    raw_scores = [max(1.0, composite_alpha_score(c)) for c in ranked]
    total_score = sum(raw_scores) or 1.0
    sector_weights = {}
    positions = []

    for c, score in zip(ranked, raw_scores):
        proposed = gross_exposure * score / total_score
        cap = min(max_single_name_weight, c.max_weight or max_single_name_weight)
        weight = min(proposed, cap)
        sector_used = sector_weights.get(c.sector, 0.0)
        if sector_used + weight > max_sector_weight:
            weight = max(0.0, max_sector_weight - sector_used)
        if weight < c.min_weight:
            weight = min(c.min_weight, cap)
        sector_weights[c.sector] = sector_weights.get(c.sector, 0.0) + weight
        positions.append({
            "symbol": c.symbol,
            "sector": c.sector,
            "alpha_score": composite_alpha_score(c),
            "target_weight": round(weight, 4),
            "current_weight": round(c.current_weight, 4),
            "rebalance_delta": round(weight - c.current_weight, 4),
            "recommendation": _weight_action(weight - c.current_weight),
            "thesis_score": c.thesis_score,
            "conviction_score": c.conviction_score,
            "risk_score": c.risk_score,
            "valuation_score": c.valuation_score,
            "momentum_score": c.momentum_score,
        })

    total_weight = sum(p["target_weight"] for p in positions)
    return {
        "status": "ok",
        "positions": positions,
        "sector_weights": {k: round(v, 4) for k, v in sector_weights.items()},
        "summary": {
            "position_count": len(positions),
            "target_gross_exposure": gross_exposure,
            "allocated_weight": round(total_weight, 4),
            "cash_reserve": round(max(0.0, 1.0 - total_weight), 4),
            "max_single_name_weight": max_single_name_weight,
            "max_sector_weight": max_sector_weight,
        },
    }

def portfolio_to_frame(result: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(result.get("positions") or [])
