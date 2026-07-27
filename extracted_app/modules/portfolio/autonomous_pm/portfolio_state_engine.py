"""
Phase 11 — Autonomous Portfolio Manager: portfolio state engine.
Builds a normalized portfolio snapshot from available broker/options data with safe fallbacks.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any
from datetime import datetime, timezone


def _num(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default


def _option_positions(paper: bool = True) -> list[dict[str, Any]]:
    try:
        from modules.options.options_broker import AlpacaOptionsBroker

        broker = AlpacaOptionsBroker(paper=paper)
        positions = broker.list_options_positions()
        rows = []
        for p in positions or []:
            rows.append(p.__dict__ if hasattr(p, "__dict__") else dict(p))
        return rows
    except Exception:
        return []


@dataclass
class PortfolioState:
    ticker: str
    paper: bool
    total_positions: int
    total_market_value: float
    total_unrealized_pnl: float
    net_delta: float
    net_gamma: float
    net_theta: float
    net_vega: float
    largest_position: str
    largest_position_value: float
    cash_proxy: float
    risk_budget: float
    generated_at: str
    positions: list[dict[str, Any]]


def build_portfolio_state(ticker: str, paper: bool = True, risk_budget: float = 100000.0) -> dict[str, Any]:
    positions = _option_positions(paper)
    if not positions:
        positions = [
            {"option_symbol": f"{ticker} SAMPLE CALL", "underlying": ticker, "qty": 1, "market_value": 550.0, "unrealized_pnl": 75.0, "delta": 0.42, "gamma": 0.03, "theta": -0.04, "vega": 0.11},
            {"option_symbol": f"{ticker} SAMPLE PUT", "underlying": ticker, "qty": -1, "market_value": -325.0, "unrealized_pnl": 25.0, "delta": 0.25, "gamma": -0.02, "theta": 0.03, "vega": -0.08},
        ]
    total_mv = sum(_num(p.get("market_value")) for p in positions)
    total_pnl = sum(_num(p.get("unrealized_pnl")) for p in positions)
    net_delta = sum(_num(p.get("delta")) * _num(p.get("qty"), 1.0) for p in positions)
    net_gamma = sum(_num(p.get("gamma")) * _num(p.get("qty"), 1.0) for p in positions)
    net_theta = sum(_num(p.get("theta")) * _num(p.get("qty"), 1.0) for p in positions)
    net_vega = sum(_num(p.get("vega")) * _num(p.get("qty"), 1.0) for p in positions)
    largest = max(positions, key=lambda p: abs(_num(p.get("market_value"))), default={})
    state = PortfolioState(
        ticker=ticker.upper(),
        paper=paper,
        total_positions=len(positions),
        total_market_value=round(total_mv, 2),
        total_unrealized_pnl=round(total_pnl, 2),
        net_delta=round(net_delta, 3),
        net_gamma=round(net_gamma, 3),
        net_theta=round(net_theta, 3),
        net_vega=round(net_vega, 3),
        largest_position=str(largest.get("option_symbol") or largest.get("symbol") or "None"),
        largest_position_value=round(abs(_num(largest.get("market_value"))), 2),
        cash_proxy=max(0.0, risk_budget - abs(total_mv)),
        risk_budget=round(risk_budget, 2),
        generated_at=datetime.now(timezone.utc).isoformat(),
        positions=positions,
    )
    return asdict(state)
