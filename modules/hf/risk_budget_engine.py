from __future__ import annotations
from typing import Any
import pandas as pd

def _num(v: Any, default: float = 0.0) -> float:
    try:
        return float(v or default)
    except Exception:
        return default

def calculate_risk_budget(positions: list[dict[str, Any]], max_portfolio_heat: float = 1.0) -> dict[str, Any]:
    rows = []
    total_heat = 0.0
    for p in positions or []:
        weight = _num(p.get("target_weight"))
        risk_score = _num(p.get("risk_score"), 50)
        heat = weight * (risk_score / 50.0)
        total_heat += heat
        rows.append({"symbol": p.get("symbol"), "sector": p.get("sector", "Unknown"), "target_weight": weight, "risk_score": risk_score, "risk_heat": round(heat, 4), "budget_status": "Over Budget" if heat > 0.12 else "OK"})
    return {"total_risk_heat": round(total_heat, 4), "max_portfolio_heat": max_portfolio_heat, "heat_utilization": round(total_heat / max_portfolio_heat, 4) if max_portfolio_heat else 0, "status": "Overheated" if total_heat > max_portfolio_heat else "Within Budget", "positions": rows}

def sector_risk_budget(positions: list[dict[str, Any]]) -> pd.DataFrame:
    if not positions:
        return pd.DataFrame()
    df = pd.DataFrame(positions)
    if df.empty:
        return df
    if "target_weight" not in df.columns:
        df["target_weight"] = 0
    if "risk_score" not in df.columns:
        df["risk_score"] = 50
    if "sector" not in df.columns:
        df["sector"] = "Unknown"
    df["risk_heat"] = df["target_weight"].astype(float) * (df["risk_score"].astype(float) / 50.0)
    return df.groupby("sector", dropna=False).agg(target_weight=("target_weight", "sum"), risk_heat=("risk_heat", "sum"), names=("symbol", "count")).reset_index()
