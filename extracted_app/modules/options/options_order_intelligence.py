"""Order intelligence helpers for Phase 7 execution fabric."""
from __future__ import annotations
from typing import Any


def recommend_order_ticket(candidate: dict[str, Any], paper: bool = True) -> dict[str, Any]:
    strategy = str(candidate.get("strategy") or "Defined Risk Spread")
    debit_credit = str(candidate.get("debit_credit") or "limit")
    confidence = float(candidate.get("confidence") or 50)
    risk = float(candidate.get("max_loss") or 0)

    limit_style = "mid-price" if confidence >= 70 else "conservative limit"
    tif = "day"
    route = "paper" if paper else "approval_required_live"
    return {
        "strategy": strategy,
        "route": route,
        "order_type": "limit",
        "limit_style": limit_style,
        "time_in_force": tif,
        "execution_note": f"Use {limit_style}; keep risk near ${risk:,.0f}; do not chase fills.",
        "debit_credit": debit_credit,
    }


def score_order_quality(candidate: dict[str, Any]) -> dict[str, Any]:
    confidence = float(candidate.get("confidence") or 50)
    liquidity = float(candidate.get("liquidity_score") or 60)
    defined = 100 if candidate.get("defined_risk", True) else 30
    risk_score = max(0, 100 - float(candidate.get("risk_score") or 50))
    score = round(confidence * 0.35 + liquidity * 0.25 + defined * 0.25 + risk_score * 0.15, 1)
    return {"order_quality_score": score, "label": "High" if score >= 75 else "Moderate" if score >= 55 else "Low"}
