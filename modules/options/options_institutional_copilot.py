"""
modules/options/options_institutional_copilot.py

Phase 3 — AI Institutional Options Copilot master orchestrator.
Builds on Phase 1 Smart Money and Phase 2 Dealer Analytics.
"""
from __future__ import annotations

from typing import Any

from modules.options.options_flow_reasoning_engine import build_flow_reasoning
from modules.options.options_positioning_analyzer import analyze_positioning
from modules.options.options_conviction_engine import score_copilot_conviction
from modules.options.options_market_maker_intelligence import interpret_market_maker_positioning
from modules.options.options_trade_recommendation_engine import recommend_institutional_option_setups


def _safe_smart_report(ticker: str) -> dict[str, Any]:
    try:
        from modules.options.options_smart_money_engine import build_options_smart_money_report
        result = build_options_smart_money_report(ticker)
        return result if isinstance(result, dict) else {"error": "Smart Money engine returned non-dict payload"}
    except Exception as exc:
        return {"error": str(exc), "ticker": ticker.upper()}


def _safe_dealer_report(ticker: str) -> dict[str, Any]:
    try:
        from modules.options.options_dealer_exposure_engine import build_dealer_exposure_report
        result = build_dealer_exposure_report(ticker)
        return result if isinstance(result, dict) else {}
    except Exception:
        try:
            from modules.options.options_dealer_exposure_engine import calculate_dealer_exposure
            result = calculate_dealer_exposure(ticker)
            return result if isinstance(result, dict) else {}
        except Exception as exc:
            return {"error": str(exc), "ticker": ticker.upper()}


def build_institutional_copilot_report(ticker: str) -> dict[str, Any]:
    smart = _safe_smart_report(ticker)
    dealer = _safe_dealer_report(ticker)

    if smart.get("error"):
        return {
            "ticker": ticker.upper(),
            "error": smart.get("error"),
            "smart_report": smart,
            "dealer_report": dealer,
        }

    reasoning = build_flow_reasoning(ticker, smart, dealer)
    positioning = analyze_positioning(ticker, smart)
    market_maker = interpret_market_maker_positioning(ticker, dealer, positioning)
    conviction = score_copilot_conviction(smart, dealer, positioning)
    recommendations = recommend_institutional_option_setups(ticker, reasoning, positioning, market_maker, conviction)
    risks = build_risk_factors(reasoning, positioning, market_maker, smart, dealer)

    return {
        "ticker": ticker.upper(),
        "institutional_thesis": reasoning,
        "positioning": positioning,
        "market_maker_intelligence": market_maker,
        "conviction": conviction,
        "trade_recommendations": recommendations,
        "risk_factors": risks,
        "smart_report": smart,
        "dealer_report": dealer,
    }


def build_risk_factors(reasoning: dict[str, Any], positioning: dict[str, Any], market_maker: dict[str, Any], smart: dict[str, Any], dealer: dict[str, Any]) -> list[str]:
    risks: list[str] = []
    if positioning.get("magnet_strength") in {"Low", None}:
        risks.append("Premium is not strongly concentrated; institutional thesis may be weaker.")
    if "short-gamma" in str(market_maker.get("hedging_regime", "")).lower():
        risks.append("Short-gamma dealer regime can amplify adverse price moves.")
    if not smart.get("top_contracts"):
        risks.append("No high-quality unusual-contract payload available; flow read may be incomplete.")
    if dealer.get("error"):
        risks.append("Dealer analytics are unavailable or degraded.")
    if "Mixed" in str(reasoning.get("direction", "")):
        risks.append("Flow direction is mixed; avoid assuming a clean directional trade.")
    return risks or ["Validate liquidity, bid/ask spreads, IV regime, event calendar, and opening-vs-closing flow before acting."]
