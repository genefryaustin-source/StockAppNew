"""Runs the Phase 10 institutional research agent team."""
from __future__ import annotations

from typing import Any

from . import fundamental_analyst_agent, valuation_analyst_agent, earnings_analyst_agent
from . import macro_analyst_agent, sector_analyst_agent, institutional_flow_agent
from . import options_analyst_agent, risk_analyst_agent, catalyst_analyst_agent, portfolio_analyst_agent

_AGENT_FUNCS = [
    fundamental_analyst_agent.run,
    valuation_analyst_agent.run,
    earnings_analyst_agent.run,
    macro_analyst_agent.run,
    sector_analyst_agent.run,
    institutional_flow_agent.run,
    options_analyst_agent.run,
    risk_analyst_agent.run,
    catalyst_analyst_agent.run,
    portfolio_analyst_agent.run,
]


def build_context(ticker: str) -> dict[str, Any]:
    """Collect optional context from existing StockApp modules without hard dependencies."""
    ctx: dict[str, Any] = {"ticker": ticker.upper()}

    # Smart Money / options flow if Phase 1 is installed.
    try:
        from modules.options.options_smart_money_engine import build_options_smart_money_report
        ctx["smart_money"] = build_options_smart_money_report(ticker)
    except Exception as exc:
        ctx["smart_money"] = {"error": str(exc)}

    # Dealer exposure if Phase 2 is installed.
    try:
        from modules.options.options_dealer_exposure_engine import build_dealer_exposure_report
        ctx["dealer"] = build_dealer_exposure_report(ticker)
    except Exception:
        ctx["dealer"] = {}

    # Volatility report if Phase 4 is installed.
    try:
        from modules.options.options_volatility_dashboard import _load_report
        ctx["volatility"] = _load_report(ticker, force_refresh=False)
    except Exception:
        ctx["volatility"] = {}

    # Conservative defaults keep the system usable when data providers are offline.
    ctx.setdefault("fundamentals", {})
    ctx.setdefault("valuation", {})
    ctx.setdefault("earnings", {})
    ctx.setdefault("macro", {})
    ctx.setdefault("sector", {})
    ctx.setdefault("risk", {})
    ctx.setdefault("catalysts", {})
    ctx.setdefault("portfolio", {})
    return ctx


def run_research_agents(ticker: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    ctx = context or build_context(ticker)
    findings = []
    errors = []
    for fn in _AGENT_FUNCS:
        try:
            finding = fn(ticker, ctx)
            findings.append(finding.to_dict() if hasattr(finding, "to_dict") else dict(finding))
        except Exception as exc:
            errors.append({"agent": getattr(fn, "__module__", str(fn)), "error": str(exc)})
    return {"ticker": ticker.upper(), "context": ctx, "findings": findings, "errors": errors}
