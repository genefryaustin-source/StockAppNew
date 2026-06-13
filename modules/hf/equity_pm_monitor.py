"""
modules/hf/equity_pm_monitor.py

Monitoring and drift detection for autonomous equity PM.
"""
from __future__ import annotations
from typing import Any
import pandas as pd


def _num(v: Any, default: float = 0.0) -> float:
    try:
        return float(v or default)
    except Exception:
        return default


def monitor_portfolio_drift(current_positions: list[dict[str, Any]], target_positions: list[dict[str, Any]], drift_threshold: float = 0.015) -> dict[str, Any]:
    current = {str(p.get("symbol")).upper(): _num(p.get("weight"), _num(p.get("current_weight"))) for p in current_positions or []}
    target = {str(p.get("symbol")).upper(): _num(p.get("target_weight")) for p in target_positions or []}

    symbols = sorted(set(current) | set(target))
    rows = []
    for sym in symbols:
        cur = current.get(sym, 0.0)
        tgt = target.get(sym, 0.0)
        drift = cur - tgt
        rows.append({
            "symbol": sym,
            "current_weight": round(cur, 4),
            "target_weight": round(tgt, 4),
            "drift": round(drift, 4),
            "status": "REBALANCE" if abs(drift) >= drift_threshold else "OK",
        })

    return {
        "drift_threshold": drift_threshold,
        "rebalance_needed": any(r["status"] == "REBALANCE" for r in rows),
        "rows": rows,
    }


def drift_frame(report: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(report.get("rows") or [])
