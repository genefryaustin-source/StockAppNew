"""Lightweight strategy backtesting/proxy simulator for Phase 5."""
from __future__ import annotations
from typing import Any
import math
import random
import pandas as pd


def _n(v: Any, d: float = 0.0) -> float:
    try:
        return float(v or d)
    except Exception:
        return d


def backtest_strategy_proxy(strategy: dict[str, Any], periods: int = 120, seed: int = 42) -> dict[str, Any]:
    """Monte Carlo-style proxy backtest using candidate metrics, not historical trades."""
    rng = random.Random(seed)
    metrics = strategy.get("metrics") or {}
    pop = _n(metrics.get("probability_profit"), 0.55)
    if pop > 1:
        pop /= 100.0
    max_profit = max(1.0, _n(metrics.get("max_profit"), 100.0))
    max_loss = max(1.0, abs(_n(metrics.get("max_loss"), 100.0)))
    values = []
    equity = 0.0
    wins = 0
    losses = 0
    peak = 0.0
    max_dd = 0.0
    for i in range(periods):
        if rng.random() < pop:
            pnl = rng.uniform(0.25, 1.0) * max_profit
            wins += 1
        else:
            pnl = -rng.uniform(0.20, 1.0) * max_loss
            losses += 1
        equity += pnl
        peak = max(peak, equity)
        max_dd = min(max_dd, equity - peak)
        values.append({"Trade": i + 1, "P&L": round(pnl, 2), "Cumulative P&L": round(equity, 2)})
    avg_win = sum(v["P&L"] for v in values if v["P&L"] > 0) / max(1, wins)
    avg_loss = abs(sum(v["P&L"] for v in values if v["P&L"] < 0) / max(1, losses))
    expectancy = (wins / periods) * avg_win - (losses / periods) * avg_loss
    return {
        "strategy_name": strategy.get("strategy_name"),
        "periods": periods,
        "win_rate": wins / max(1, periods),
        "total_pnl": round(equity, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "expectancy": round(expectancy, 2),
        "max_drawdown": round(max_dd, 2),
        "trades": values,
    }


def backtest_to_frame(result: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(result.get("trades") or [])
