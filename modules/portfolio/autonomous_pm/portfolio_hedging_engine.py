"""Hedging candidate generator for autonomous portfolio management."""
from __future__ import annotations
from typing import Any


def _num(v: Any, d: float = 0.0) -> float:
    try: return float(v if v is not None else d)
    except Exception: return d


def generate_hedge_candidates(ticker: str, state: dict[str, Any]) -> list[dict[str, Any]]:
    delta = _num(state.get("net_delta"))
    vega = _num(state.get("net_vega"))
    hedges = []
    if delta > 0.5:
        hedges.append({"hedge": "Buy put spread", "underlying": ticker.upper(), "purpose": "Reduce downside delta", "urgency": "Medium"})
    if delta < -0.5:
        hedges.append({"hedge": "Buy call spread", "underlying": ticker.upper(), "purpose": "Reduce upside short exposure", "urgency": "Medium"})
    if abs(vega) > 1.0:
        hedges.append({"hedge": "Calendar/diagonal adjustment", "underlying": ticker.upper(), "purpose": "Normalize vega exposure", "urgency": "Low"})
    if not hedges:
        hedges.append({"hedge": "No hedge required", "underlying": ticker.upper(), "purpose": "Portfolio inside default hedge bands", "urgency": "Low"})
    return hedges
