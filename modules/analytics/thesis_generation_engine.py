"""
modules/analytics/thesis_generation_engine.py

Institutional AI thesis generation engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, UTC
from typing import Any, Dict, List, Optional
import math


@dataclass
class InvestmentThesis:
    symbol: str
    conviction_label: str
    thesis: str
    bull_case: str
    bear_case: str
    risk_outlook: str
    macro_overlay: str
    confidence_summary: str
    generated_at: datetime


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


def _list_text(items: Optional[List[str]], fallback: str) -> str:
    if not items:
        return fallback
    return ", ".join(sorted(set(str(x) for x in items if x)))


def _conviction_label(
    ai_score: float,
    consensus_score: float,
    risk_pressure: float,
    market_regime: str,
) -> str:

    if ai_score >= 75 and consensus_score >= 70 and risk_pressure < 55:
        return "High Conviction AI Favorite"

    if ai_score >= 65 and consensus_score >= 60:
        return "Institutional Momentum Candidate"

    if ai_score >= 55 and risk_pressure < 60:
        return "Constructive Watchlist Candidate"

    if risk_pressure >= 70:
        return "Risk Deterioration Candidate"

    if market_regime in {"bear", "panic"}:
        return "Macro-Sensitive Candidate"

    return "Neutral AI Research Candidate"


def generate_bull_case(
    symbol: str,
    bullish_factors: Optional[List[str]],
    sentiment_tone: str,
    earnings_tone: str,
) -> str:

    factors = _list_text(
        bullish_factors,
        "no dominant bullish factors detected",
    )

    return (
        f"{symbol} bullish case is supported by {factors}. "
        f"News tone is currently {sentiment_tone}, while earnings language "
        f"is classified as {earnings_tone}."
    )


def generate_bear_case(
    symbol: str,
    bearish_factors: Optional[List[str]],
    risk_flags: Optional[List[str]],
) -> str:

    negatives = _list_text(
        bearish_factors,
        "no dominant bearish factors detected",
    )

    risks = _list_text(
        risk_flags,
        "no major risk flags detected",
    )

    return (
        f"{symbol} bear case centers on {negatives}. "
        f"Current risk flags include {risks}."
    )


def generate_risk_outlook(
    symbol: str,
    risk_pressure: float,
    risk_flags: Optional[List[str]],
) -> str:

    risks = _list_text(
        risk_flags,
        "no major flagged risks",
    )

    if risk_pressure >= 70:
        level = "elevated"
    elif risk_pressure >= 50:
        level = "moderate"
    else:
        level = "controlled"

    return (
        f"{symbol} has a {level} risk outlook. "
        f"Primary risk indicators: {risks}."
    )


def generate_macro_overlay(
    market_regime: str,
    volatility_level: str,
    momentum_state: str,
) -> str:

    return (
        f"Macro backdrop is classified as {market_regime}. "
        f"Volatility is {volatility_level}, and market momentum is "
        f"{momentum_state}."
    )


def generate_investment_thesis(
    symbol: str,
    ai_score: Any = None,
    ai_confidence: Any = None,
    consensus_score: Any = None,
    consensus_confidence: Any = None,
    bullish_factors: Optional[List[str]] = None,
    bearish_factors: Optional[List[str]] = None,
    risk_flags: Optional[List[str]] = None,
    sentiment_tone: str = "neutral",
    earnings_tone: str = "stable",
    guidance_score: Any = None,
    ceo_confidence: Any = None,
    risk_pressure: Any = None,
    market_regime: str = "neutral",
    volatility_level: str = "unknown",
    momentum_state: str = "mixed",
) -> InvestmentThesis:

    ai_score_f = _safe_float(ai_score, 50.0)
    ai_conf_f = _safe_float(ai_confidence, 50.0)
    consensus_f = _safe_float(consensus_score, 50.0)
    consensus_conf_f = _safe_float(consensus_confidence, 50.0)
    guidance_f = _safe_float(guidance_score, 50.0)
    ceo_conf_f = _safe_float(ceo_confidence, 50.0)
    risk_f = _safe_float(risk_pressure, 50.0)

    conviction = _conviction_label(
        ai_score=ai_score_f,
        consensus_score=consensus_f,
        risk_pressure=risk_f,
        market_regime=market_regime,
    )

    bull_case = generate_bull_case(
        symbol=symbol,
        bullish_factors=bullish_factors,
        sentiment_tone=sentiment_tone,
        earnings_tone=earnings_tone,
    )

    bear_case = generate_bear_case(
        symbol=symbol,
        bearish_factors=bearish_factors,
        risk_flags=risk_flags,
    )

    risk_outlook = generate_risk_outlook(
        symbol=symbol,
        risk_pressure=risk_f,
        risk_flags=risk_flags,
    )

    macro_overlay = generate_macro_overlay(
        market_regime=market_regime,
        volatility_level=volatility_level,
        momentum_state=momentum_state,
    )

    confidence_summary = (
        f"AI confidence is {round(ai_conf_f, 2)} and multi-agent consensus "
        f"confidence is {round(consensus_conf_f, 2)}. Earnings guidance score "
        f"is {round(guidance_f, 2)}, CEO confidence is {round(ceo_conf_f, 2)}, "
        f"and risk pressure is {round(risk_f, 2)}."
    )

    thesis = (
        f"{symbol} is classified as a {conviction}. "
        f"The AI score is {round(ai_score_f, 2)} and multi-agent consensus "
        f"score is {round(consensus_f, 2)}. "
        f"{bull_case} {bear_case} {risk_outlook} {macro_overlay} "
        f"{confidence_summary}"
    )

    return InvestmentThesis(
        symbol=symbol,
        conviction_label=conviction,
        thesis=thesis,
        bull_case=bull_case,
        bear_case=bear_case,
        risk_outlook=risk_outlook,
        macro_overlay=macro_overlay,
        confidence_summary=confidence_summary,
        generated_at=datetime.now(UTC),
    )