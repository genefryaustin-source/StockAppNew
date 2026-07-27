"""
Phase 10 — Multi-Agent Institutional Research Analysts
Agent registry and shared utilities.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Callable
import math


@dataclass
class AgentFinding:
    agent: str
    rating: str
    score: float
    confidence: float
    summary: str
    positives: list[str]
    risks: list[str]
    evidence: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


RATING_SCALE = ["Strong Sell", "Sell", "Reduce", "Hold", "Buy", "Strong Buy"]


def clamp(value: Any, low: float = 0.0, high: float = 100.0, default: float = 50.0) -> float:
    try:
        x = float(value)
        if math.isnan(x):
            return default
        return max(low, min(high, x))
    except Exception:
        return default


def rating_from_score(score: float) -> str:
    score = clamp(score)
    if score >= 85:
        return "Strong Buy"
    if score >= 68:
        return "Buy"
    if score >= 54:
        return "Hold"
    if score >= 40:
        return "Reduce"
    if score >= 25:
        return "Sell"
    return "Strong Sell"


def confidence_from_evidence(*values: Any) -> float:
    populated = 0
    for v in values:
        if v is None:
            continue
        if isinstance(v, (list, tuple, dict, set)) and len(v) == 0:
            continue
        populated += 1
    return clamp(35 + populated * 10, 20, 95, 45)


AGENT_REGISTRY: dict[str, str] = {
    "fundamental": "Fundamental Analyst",
    "valuation": "Valuation Analyst",
    "earnings": "Earnings Analyst",
    "macro": "Macro Analyst",
    "sector": "Sector Analyst",
    "institutional_flow": "Institutional Flow Analyst",
    "options": "Options Analyst",
    "risk": "Risk Analyst",
    "catalyst": "Catalyst Analyst",
    "portfolio": "Portfolio Analyst",
}


def list_agents() -> list[dict[str, str]]:
    return [{"key": k, "name": v} for k, v in AGENT_REGISTRY.items()]
