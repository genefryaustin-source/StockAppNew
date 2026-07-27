"""
modules/hf/agents/base_agent.py

Shared primitives for Stock HF-2 multi-agent equity research analysts.
Designed to be deterministic, UI-safe, and dependency-light.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any


@dataclass
class AgentSignal:
    agent: str
    ticker: str
    rating: str
    score: float
    confidence: float
    thesis: str
    positives: list[str]
    risks: list[str]
    data_quality: str = "partial"
    generated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if not data.get("generated_at"):
            data["generated_at"] = datetime.now(timezone.utc).isoformat()
        return data


RATING_ORDER = ["Strong Sell", "Sell", "Reduce", "Hold", "Buy", "Strong Buy"]


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    try:
        return max(low, min(high, float(value)))
    except Exception:
        return low


def score_to_rating(score: float) -> str:
    score = clamp(score)
    if score >= 85:
        return "Strong Buy"
    if score >= 68:
        return "Buy"
    if score >= 52:
        return "Hold"
    if score >= 38:
        return "Reduce"
    if score >= 20:
        return "Sell"
    return "Strong Sell"


def safe_num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def normalize_context(context: dict[str, Any] | None) -> dict[str, Any]:
    return context if isinstance(context, dict) else {}
