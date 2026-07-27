"""
Sprint 4 Phase 5 — Institutional Trade Factory.

Master orchestrator for generating, ranking, and templating institutional
options trade ideas from Sprint 4 intelligence layers.
"""
from __future__ import annotations

from typing import Any

from modules.options.options_opportunity_scanner import scan_option_opportunities, infer_directional_bias
from modules.options.options_strategy_factory import build_strategy_templates
from modules.options.options_trade_ranking_engine import rank_trade_candidates


def build_trade_factory_report(
    ticker: str,
    chain_data: dict[str, Any] | None,
    intelligence_report: dict[str, Any] | None = None,
    flow_report: dict[str, Any] | None = None,
    market_maker_report: dict[str, Any] | None = None,
    volatility_report: dict[str, Any] | None = None,
    max_candidates: int = 20,
) -> dict[str, Any]:
    bias = infer_directional_bias(
        intelligence_report=intelligence_report,
        flow_report=flow_report,
        market_maker_report=market_maker_report,
        volatility_report=volatility_report,
    )

    candidates = scan_option_opportunities(
        ticker=ticker,
        chain_data=chain_data,
        intelligence_report=intelligence_report,
        flow_report=flow_report,
        market_maker_report=market_maker_report,
        volatility_report=volatility_report,
        max_candidates=max_candidates,
    )

    ranked = rank_trade_candidates(
        candidates,
        intelligence_report=intelligence_report,
        flow_report=flow_report,
        market_maker_report=market_maker_report,
        volatility_report=volatility_report,
    )

    templates = build_strategy_templates(ranked)

    top = ranked[0] if ranked else None

    if top:
        summary = (
            f"Top idea: {top.get('strategy')} ({top.get('direction')}) "
            f"score {top.get('rank_score')}/100. "
            f"Bias: {bias.get('bias')} ({bias.get('direction_score')}/100)."
        )
    else:
        summary = "No institutional trade candidates generated."

    return {
        "available": bool(ranked),
        "ticker": ticker.upper(),
        "bias": bias,
        "candidates": ranked,
        "templates": templates,
        "top_trade": top,
        "summary": summary,
    }
