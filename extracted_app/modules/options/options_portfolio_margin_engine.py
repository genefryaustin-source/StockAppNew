"""Margin and capital utilization approximations for options portfolios."""
from __future__ import annotations
from typing import Any


def _n(v: Any, d: float = 0.0) -> float:
    try:
        return float(v or d)
    except Exception:
        return d


def estimate_margin_requirement(positions: list[dict[str, Any]], account: dict[str, Any] | None = None) -> dict[str, Any]:
    account = account or {}
    requirement = 0.0
    max_single = 0.0
    for p in positions or []:
        qty = abs(_n(p.get("qty")))
        strike = _n(p.get("strike"))
        mv = abs(_n(p.get("market_value")))
        opt_type = str(p.get("option_type") or "").lower()
        # Conservative approximation: short options require notional cushion.
        req = max(mv, strike * qty * 100 * 0.20 if qty and strike else mv)
        requirement += req
        max_single = max(max_single, req)

    buying_power = _n(account.get("options_buying_power") or account.get("buying_power"))
    equity = _n(account.get("equity") or account.get("portfolio_value"))
    base = buying_power or equity or requirement or 1.0
    util = requirement / base if base else 0.0
    return {
        "estimated_margin_requirement": requirement,
        "largest_position_margin": max_single,
        "buying_power": buying_power,
        "equity": equity,
        "capital_utilization": util,
        "risk_utilization_label": "High" if util > 0.75 else "Moderate" if util > 0.40 else "Low",
    }


def load_account_snapshot(paper: bool = True) -> dict[str, Any]:
    try:
        from modules.options.options_broker import AlpacaOptionsBroker
        return AlpacaOptionsBroker(paper=paper).get_account() or {}
    except Exception:
        return {}
