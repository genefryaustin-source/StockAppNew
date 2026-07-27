"""
modules/options/options_flow_reasoning_engine.py

Phase 3 — Institutional Options Copilot flow reasoning engine.
Turns Phase 1 Smart Money and Phase 2 Dealer Analytics data into structured,
plain-English institutional flow interpretations.
"""
from __future__ import annotations

from typing import Any


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value or default)
    except Exception:
        return default


def _label_direction(score: float) -> str:
    if score >= 70:
        return "Bullish Institutional Accumulation"
    if score >= 56:
        return "Moderately Bullish Flow"
    if score <= 30:
        return "Bearish Institutional Positioning"
    if score <= 44:
        return "Moderately Bearish Flow"
    return "Mixed / Neutral Positioning"


def build_flow_reasoning(ticker: str, smart_report: dict[str, Any], dealer_report: dict[str, Any] | None = None) -> dict[str, Any]:
    dealer_report = dealer_report or {}
    flow = smart_report.get("flow", {}) or {}
    sentiment = smart_report.get("sentiment", {}) or {}
    conviction = smart_report.get("conviction_score", {}) or {}
    whales = smart_report.get("whale_summary", {}) or {}
    sweeps = smart_report.get("sweep_summary", {}) or {}
    top_contracts = smart_report.get("top_contracts", []) or []

    total_premium = _num(flow.get("total_premium"))
    net_premium = _num(flow.get("net_premium"))
    call_pct = _num(flow.get("call_premium_pct"))
    put_pct = _num(flow.get("put_premium_pct"))
    sentiment_score = _num(sentiment.get("score"), 50)
    conviction_score = _num(conviction.get("score"), 0)

    direction_score = sentiment_score
    if total_premium > 0:
        direction_score += max(-12, min(12, net_premium / total_premium * 20))
    if _num(whales.get("call_whales")) > _num(whales.get("put_whales")):
        direction_score += 5
    elif _num(whales.get("put_whales")) > _num(whales.get("call_whales")):
        direction_score -= 5

    direction_score = max(0, min(100, round(direction_score, 1)))
    direction = _label_direction(direction_score)

    top = top_contracts[0] if top_contracts else {}
    premium_read = "Calls dominating premium" if call_pct > 0.6 else "Puts dominating premium" if put_pct > 0.6 else "Balanced premium flow"
    whale_read = f"{whales.get('whale_count', 0)} whale/block candidates and {sweeps.get('sweep_count', 0)} sweep candidates detected."

    dealer_context = "Dealer data unavailable."
    if dealer_report:
        gex = dealer_report.get("dealer_summary", {}).get("net_gex") or dealer_report.get("net_gex")
        z = dealer_report.get("dealer_summary", {}).get("zero_gamma") or dealer_report.get("zero_gamma")
        dealer_context = f"Dealer context: net GEX={gex if gex is not None else 'N/A'}, zero-gamma={z if z is not None else 'N/A'}."

    observations = [
        f"{premium_read}: call premium {call_pct:.0%}, put premium {put_pct:.0%}.",
        whale_read,
        f"Institutional sentiment score is {sentiment_score:.1f}/100 and conviction score is {conviction_score:.1f}/100.",
        dealer_context,
    ]
    if top:
        observations.insert(0, f"Largest contract by premium: {top.get('type', 'N/A')} {top.get('strike', 'N/A')} exp {top.get('expiry', 'N/A')} with estimated premium {top.get('premium_fmt') or top.get('premium_est', 'N/A')}.")

    return {
        "ticker": ticker.upper(),
        "direction": direction,
        "direction_score": direction_score,
        "premium_read": premium_read,
        "whale_read": whale_read,
        "dealer_context": dealer_context,
        "observations": observations,
        "summary": f"{ticker.upper()} shows {direction.lower()} with {premium_read.lower()} and conviction {conviction_score:.1f}/100.",
    }
