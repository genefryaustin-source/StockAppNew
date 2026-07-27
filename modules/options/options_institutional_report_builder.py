"""
modules/options/options_institutional_report_builder.py

Computes the real upstream reports that several Institutional
meta-aggregator dashboards (Trade Selection, CIO Dashboard, and
others) depend on but, confirmed via direct tracing, were never
actually being computed and passed in from options_ui.py -- every one
of them defaulted to None, meaning e.g. Trade Selection always showed
zero candidates and CIO Dashboard always showed default/meaningless
scores, regardless of real portfolio or market conditions.

Each report is computed independently and defensively (a failure in
one doesn't block the others) from real data already available in
this app: real positions (via load_portfolio_positions(), the same
broker-backed source already verified correct elsewhere), real
account cash (via the broker's own account snapshot), and the real
options chain already loaded for the current ticker.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import pandas as pd

logger = logging.getLogger(__name__)


def _safe_build(label: str, fn, *args, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Never lets one report's failure take down the others -- a
    dashboard combining 5-10 of these should degrade to "this one
    input is missing" for the failed piece, not crash the whole page.
    """
    try:
        return fn(*args, **kwargs)
    except Exception:
        logger.exception("Failed to build %s report", label)
        return None


def build_shared_institutional_reports(
    *, ticker: str, paper: bool, chain_data: Optional[dict] = None,
) -> Dict[str, Any]:
    from modules.options.options_portfolio_engine import load_portfolio_positions
    from modules.options.options_broker import AlpacaOptionsBroker
    from modules.options.options_data_service import get_options_chain

    from modules.options.options_cash_secured_put_factory_engine import build_cash_secured_put_report
    from modules.options.options_covered_call_factory_engine import build_covered_call_candidates
    from modules.options.options_wheel_engine import build_wheel_command_report
    from modules.options.options_income_engine import build_income_intelligence_report
    from modules.options.options_roll_engine import build_rolling_intelligence_report
    from modules.options.options_assignment_engine import build_assignment_expiration_report
    from modules.options.options_income_command_center import build_institutional_income_command_report
    from modules.options.options_volatility_surface_engine import build_volatility_surface_report
    from modules.options.options_volatility_regime_engine import build_volatility_regime_report
    from modules.options.options_term_structure_engine import build_term_structure_report
    from modules.options.options_skew_engine import build_skew_intelligence_report
    from modules.options.options_volatility_command_center import build_volatility_command_center_report

    positions = load_portfolio_positions(ticker=ticker, paper=paper)

    try:
        account = AlpacaOptionsBroker(paper=paper).get_account()
        portfolio_cash = float(account.get("cash") or account.get("buying_power") or 100000.0)
    except Exception:
        logger.exception("Failed to fetch account cash for institutional report building")
        portfolio_cash = 100000.0

    if chain_data is None:
        chain_data = get_options_chain(ticker) if ticker else None

    # Position-based reports
    covered_call_report = _safe_build("covered_call", build_covered_call_candidates, positions=positions)
    wheel_report = _safe_build("wheel", build_wheel_command_report, positions)
    income_report = _safe_build("income", build_income_intelligence_report, positions)
    roll_report = _safe_build("roll", build_rolling_intelligence_report, positions)
    assignment_report = _safe_build("assignment", build_assignment_expiration_report, positions)

    # Chain-based reports
    csp_report = (
        _safe_build("csp", build_cash_secured_put_report, chain_data, portfolio_cash=portfolio_cash)
        if chain_data else None
    )
    surface_report = _safe_build("vol_surface", build_volatility_surface_report, chain_data) if chain_data else None
    regime_report = _safe_build("vol_regime", build_volatility_regime_report, chain_data) if chain_data else None
    term_report = _safe_build("term_structure", build_term_structure_report, chain_data) if chain_data else None
    skew_report = _safe_build("skew", build_skew_intelligence_report, chain_data) if chain_data else None

    # Second-layer aggregates, built from the reports just computed above
    income_command_report = _safe_build(
        "income_command", build_institutional_income_command_report,
        income_report=income_report, wheel_report=wheel_report, covered_call_report=covered_call_report,
        csp_report=csp_report, roll_report=roll_report, assignment_report=assignment_report,
    )
    volatility_command_report = _safe_build(
        "volatility_command", build_volatility_command_center_report,
        surface_report=surface_report, regime_report=regime_report, term_report=term_report, skew_report=skew_report,
    )

    return {
        "positions": positions,
        "portfolio_cash": portfolio_cash,
        "csp_report": csp_report,
        "covered_call_report": covered_call_report,
        "wheel_report": wheel_report,
        "income_report": income_report,
        "roll_report": roll_report,
        "assignment_report": assignment_report,
        "income_command_report": income_command_report,
        "surface_report": surface_report,
        "regime_report": regime_report,
        "term_report": term_report,
        "skew_report": skew_report,
        "volatility_command_report": volatility_command_report,
    }


def build_cio_level_reports(*, ticker: str, paper: bool, chain_data: Optional[dict] = None) -> Dict[str, Any]:
    """
    Builds the full set of reports the CIO Dashboard depends on --
    another confirmed severe case (always showed default/meaningless
    scores, every one of its 6 report inputs defaulted to None). This
    reuses build_shared_institutional_reports() for the reports common
    to both, then builds the additional layer CIO-specific reports
    need: portfolio risk/greeks/guardrails/construction (from real
    positions), dealer/gamma/hedging/liquidity-provider (from the real
    options chain, for Market Maker Command), then the second-layer
    aggregates (Portfolio Optimization, Market Maker Command, Auto
    Income, Trade Selection, Risk Rebalancing) that feed directly into
    the CIO report itself.
    """
    from modules.options.options_portfolio_risk_engine import build_portfolio_risk_report
    from modules.options.options_greeks_exposure_engine import build_greeks_exposure_report
    from modules.options.options_risk_guardrails_engine import evaluate_portfolio_guardrails
    from modules.options.options_portfolio_construction_engine import build_portfolio_construction_report
    from modules.options.options_dealer_positioning_engine import build_dealer_positioning_report
    from modules.options.options_gamma_exposure_engine import build_gamma_exposure_report
    from modules.options.options_dealer_hedging_flow_engine import build_dealer_hedging_flow_report
    from modules.options.options_liquidity_provider_engine import build_liquidity_provider_report
    from modules.options.options_market_maker_command_center import build_market_maker_command_center_report
    from modules.options.options_portfolio_optimization_ai import build_portfolio_optimization_report
    from modules.options.options_autonomous_income_management import build_autonomous_income_management_report
    from modules.options.options_autonomous_trade_selection import build_autonomous_trade_selection_report
    from modules.options.options_autonomous_risk_rebalancing import build_autonomous_risk_rebalancing_report
    from modules.options.options_institutional_cio_engine import build_institutional_cio_report

    shared = build_shared_institutional_reports(ticker=ticker, paper=paper, chain_data=chain_data)
    positions = shared["positions"]

    risk_report = _safe_build("portfolio_risk", build_portfolio_risk_report, positions)
    greeks_report = _safe_build("greeks", build_greeks_exposure_report, positions)
    guardrails_report = _safe_build("guardrails", evaluate_portfolio_guardrails, risk_report) if risk_report else None
    construction_report = _safe_build("construction", build_portfolio_construction_report, positions)

    underlying_price = chain_data.get("underlying_price") if isinstance(chain_data, dict) else None
    dealer_report = _safe_build("dealer_positioning", build_dealer_positioning_report, chain_data, underlying_price) if chain_data else None
    gamma_report = _safe_build("gamma_exposure", build_gamma_exposure_report, chain_data, underlying_price) if chain_data else None
    hedging_report = _safe_build("hedging_flow", build_dealer_hedging_flow_report, chain_data, underlying_price) if chain_data else None
    liquidity_provider_report = _safe_build("liquidity_provider", build_liquidity_provider_report, chain_data) if chain_data else None

    market_maker_report = _safe_build(
        "market_maker_command", build_market_maker_command_center_report,
        dealer_report=dealer_report, gamma_report=gamma_report,
        hedging_report=hedging_report, liquidity_report=liquidity_provider_report,
    )

    portfolio_optimization_report = _safe_build(
        "portfolio_optimization", build_portfolio_optimization_report, positions,
        risk_report=risk_report, construction_report=construction_report, income_report=shared["income_report"],
        liquidity_report=liquidity_provider_report, market_maker_report=market_maker_report,
        volatility_report=shared["volatility_command_report"],
    )
    auto_income_report = _safe_build(
        "auto_income", build_autonomous_income_management_report,
        covered_call_report=shared["covered_call_report"], csp_report=shared["csp_report"],
        wheel_report=shared["wheel_report"], income_report=shared["income_report"],
    )
    trade_selection_report = _safe_build(
        "trade_selection", build_autonomous_trade_selection_report,
        portfolio_value=shared["portfolio_cash"], csp_report=shared["csp_report"],
        covered_call_report=shared["covered_call_report"], wheel_report=shared["wheel_report"],
        income_command_report=shared["income_command_report"],
        volatility_command_report=shared["volatility_command_report"], market_maker_report=market_maker_report,
    )
    risk_rebalancing_report = _safe_build(
        "risk_rebalancing", build_autonomous_risk_rebalancing_report, positions,
        risk_report=risk_report, greeks_report=greeks_report, guardrails_report=guardrails_report,
        liquidity_report=liquidity_provider_report, market_maker_report=market_maker_report,
        volatility_report=shared["volatility_command_report"],
    )

    return {
        "portfolio_optimization_report": portfolio_optimization_report,
        "trade_selection_report": trade_selection_report,
        "risk_rebalancing_report": risk_rebalancing_report,
        "auto_income_report": auto_income_report,
        "volatility_report": shared["volatility_command_report"],
        "market_maker_report": market_maker_report,
        # Intermediate reports, also needed directly by other dashboards
        # (Risk Rebalancing, Portfolio Optimization AI, Guardrails) that
        # take these as their own parameters rather than computing them
        # internally.
        "positions": positions,
        "risk_report": risk_report,
        "greeks_report": greeks_report,
        "guardrails_report": guardrails_report,
        "construction_report": construction_report,
        "liquidity_provider_report": liquidity_provider_report,
        "income_report": shared["income_report"],
    }