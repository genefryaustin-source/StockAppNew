"""
modules/options/options_portfolio_engine.py

Phase 6 — Options Portfolio Command Center core portfolio engine.
Normalizes live broker positions, simulated positions, and raw dictionaries into a
consistent portfolio model for risk, exposure, stress testing, sizing, allocation,
and AI review.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any
import math
import re

import pandas as pd


@dataclass
class NormalizedOptionPosition:
    option_symbol: str
    underlying: str
    option_type: str
    strike: float
    expiry: str
    dte: int
    qty: float
    avg_cost: float
    mark_price: float
    market_value: float
    unrealized_pnl: float
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    strategy_name: str = "Single Leg"
    source: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, float) and math.isnan(value):
            return default
        return float(value)
    except Exception:
        return default


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return default


def _dte(expiry: str) -> int:
    try:
        exp = datetime.fromisoformat(str(expiry)[:10]).replace(tzinfo=timezone.utc)
        return max(0, (exp - datetime.now(timezone.utc)).days)
    except Exception:
        return 0


def parse_occ_symbol(symbol: str) -> dict[str, Any]:
    """Best-effort OCC parser. Works for common symbols like AAPL240119C00150000."""
    s = str(symbol or "").strip().upper()
    match = re.match(r"^([A-Z]{1,6})(\d{6})([CP])(\d{8})$", s)
    if not match:
        return {"underlying": "", "expiry": "", "option_type": "", "strike": 0.0}
    underlying, yymmdd, cp, strike_raw = match.groups()
    year = 2000 + int(yymmdd[:2])
    month = int(yymmdd[2:4])
    day = int(yymmdd[4:6])
    strike = int(strike_raw) / 1000.0
    return {
        "underlying": underlying,
        "expiry": f"{year:04d}-{month:02d}-{day:02d}",
        "option_type": "call" if cp == "C" else "put",
        "strike": strike,
    }


def normalize_position(raw: Any, fallback_underlying: str = "") -> NormalizedOptionPosition:
    if hasattr(raw, "__dict__"):
        row = dict(raw.__dict__)
    elif isinstance(raw, dict):
        row = dict(raw)
    else:
        row = {}

    symbol = str(row.get("option_symbol") or row.get("symbol") or row.get("contract") or "")
    parsed = parse_occ_symbol(symbol)
    underlying = str(row.get("underlying") or parsed.get("underlying") or fallback_underlying or "").upper()
    option_type = str(row.get("option_type") or row.get("type") or parsed.get("option_type") or "").lower()
    expiry = str(row.get("expiry") or row.get("expiration") or parsed.get("expiry") or "")[:10]
    strike = _num(row.get("strike"), _num(parsed.get("strike")))

    qty = _num(row.get("qty") or row.get("quantity") or row.get("contracts"), 0.0)
    avg_cost = _num(row.get("avg_cost") or row.get("average_price") or row.get("cost_basis"), 0.0)
    mark = _num(row.get("mark_price") or row.get("current_price") or row.get("last") or row.get("lastPrice"), avg_cost)
    market_value = _num(row.get("market_value"), mark * qty * 100)
    unrealized = _num(row.get("unrealized_pnl") or row.get("unrealized_pl"), (mark - avg_cost) * qty * 100)

    multiplier = 100.0 * qty
    return NormalizedOptionPosition(
        option_symbol=symbol or f"{underlying} OPTION",
        underlying=underlying,
        option_type=option_type,
        strike=strike,
        expiry=expiry,
        dte=_int(row.get("dte"), _dte(expiry)),
        qty=qty,
        avg_cost=avg_cost,
        mark_price=mark,
        market_value=market_value,
        unrealized_pnl=unrealized,
        delta=_num(row.get("delta")) * multiplier,
        gamma=_num(row.get("gamma")) * multiplier,
        theta=_num(row.get("theta")) * multiplier,
        vega=_num(row.get("vega")) * multiplier,
        rho=_num(row.get("rho")) * multiplier,
        strategy_name=str(row.get("strategy_name") or row.get("strategy") or "Single Leg"),
        source=str(row.get("source") or "unknown"),
    )


def normalize_positions(positions: list[Any] | None, fallback_underlying: str = "") -> list[dict[str, Any]]:
    return [normalize_position(p, fallback_underlying).to_dict() for p in (positions or [])]


def get_broker_option_positions(paper: bool = True, fallback_underlying: str = "") -> list[dict[str, Any]]:
    """Load positions from the existing Alpaca broker adapter if available."""
    try:
        from modules.options.options_broker import AlpacaOptionsBroker
        broker = AlpacaOptionsBroker(paper=paper)
        if hasattr(broker, "list_options_positions"):
            raw = broker.list_options_positions()
        elif hasattr(broker, "get_positions"):
            raw = broker.get_positions()
        else:
            raw = []
        return normalize_positions(raw, fallback_underlying)
    except Exception:
        return []


def get_session_simulated_positions(fallback_underlying: str = "") -> list[dict[str, Any]]:
    try:
        import streamlit as st
        raw = st.session_state.get("options_sim_trades", [])
        positions = []
        for item in raw:
            row = dict(item)
            row.setdefault("option_symbol", row.get("contract", f"{fallback_underlying} SIM"))
            row.setdefault("underlying", fallback_underlying)
            row.setdefault("qty", row.get("qty", 1))
            row.setdefault("avg_cost", row.get("price", 0))
            row.setdefault("mark_price", row.get("price", 0))
            row.setdefault("source", "simulated")
            positions.append(row)
        return normalize_positions(positions, fallback_underlying)
    except Exception:
        return []


def load_portfolio_positions(ticker: str = "", paper: bool = True) -> list[dict[str, Any]]:
    positions = get_broker_option_positions(paper=paper, fallback_underlying=ticker)
    if positions:
        return positions
    return get_session_simulated_positions(fallback_underlying=ticker)


def positions_frame(positions: list[dict[str, Any]]) -> pd.DataFrame:
    if not positions:
        return pd.DataFrame()
    df = pd.DataFrame(positions)
    preferred = [
        "option_symbol", "underlying", "option_type", "strike", "expiry", "dte", "qty",
        "avg_cost", "mark_price", "market_value", "unrealized_pnl",
        "delta", "gamma", "theta", "vega", "rho", "strategy_name", "source",
    ]
    return df[[c for c in preferred if c in df.columns]].copy()
