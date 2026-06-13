"""Stress testing for options portfolios."""
from __future__ import annotations
from typing import Any
import pandas as pd


def _n(v: Any, d: float = 0.0) -> float:
    try:
        return float(v or d)
    except Exception:
        return d


def run_portfolio_stress_test(positions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scenarios = [
        {"scenario": "Market Rally +5%", "price_move": 0.05, "iv_move": -0.05},
        {"scenario": "Market Rally +10%", "price_move": 0.10, "iv_move": -0.08},
        {"scenario": "Market Selloff -5%", "price_move": -0.05, "iv_move": 0.10},
        {"scenario": "Market Selloff -10%", "price_move": -0.10, "iv_move": 0.18},
        {"scenario": "Crash Shock -20%", "price_move": -0.20, "iv_move": 0.35},
        {"scenario": "IV Crush -25 vol pts", "price_move": 0.00, "iv_move": -0.25},
        {"scenario": "IV Expansion +25 vol pts", "price_move": 0.00, "iv_move": 0.25},
        {"scenario": "Earnings Shock +8%", "price_move": 0.08, "iv_move": -0.20},
        {"scenario": "Earnings Shock -8%", "price_move": -0.08, "iv_move": -0.20},
    ]
    results = []
    for sc in scenarios:
        pnl = 0.0
        for p in positions or []:
            delta = _n(p.get("delta"))
            gamma = _n(p.get("gamma"))
            vega = _n(p.get("vega"))
            theta = _n(p.get("theta"))
            strike = _n(p.get("strike"), 100.0) or 100.0
            move_dollars = strike * sc["price_move"]
            pnl += delta * move_dollars
            pnl += 0.5 * gamma * (move_dollars ** 2)
            pnl += vega * (sc["iv_move"] * 100)
            pnl += theta * 5  # five trading-day stress window
        results.append({
            "scenario": sc["scenario"],
            "price_move_pct": sc["price_move"],
            "iv_move": sc["iv_move"],
            "estimated_pnl": round(pnl, 2),
        })
    return results


def stress_test_frame(positions: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(run_portfolio_stress_test(positions))
