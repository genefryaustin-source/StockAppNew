from __future__ import annotations
from typing import Any
import pandas as pd

FACTOR_SECTOR_MAP = {
    "Technology": {"growth": 0.8, "quality": 0.7, "cyclical": 0.5},
    "Healthcare": {"quality": 0.7, "defensive": 0.5, "growth": 0.4},
    "Financials": {"value": 0.6, "cyclical": 0.7, "rates": 0.8},
    "Energy": {"value": 0.7, "cyclical": 0.8, "inflation": 0.8},
    "Consumer Defensive": {"defensive": 0.9, "quality": 0.6},
    "Utilities": {"defensive": 0.8, "rates": -0.5},
}

def _num(v: Any, default: float = 0.0) -> float:
    try:
        return float(v or default)
    except Exception:
        return default

def estimate_factor_exposure(positions: list[dict[str, Any]]) -> dict[str, Any]:
    exposures = {}
    for p in positions or []:
        sector = str(p.get("sector") or "Unknown")
        weight = _num(p.get("target_weight"))
        factors = FACTOR_SECTOR_MAP.get(sector, {"market": 1.0})
        for factor, beta in factors.items():
            exposures[factor] = exposures.get(factor, 0.0) + weight * beta
    return {"factor_exposures": {k: round(v, 4) for k, v in sorted(exposures.items())}, "dominant_factor": max(exposures, key=exposures.get) if exposures else "market"}

def factor_frame(report: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame([{"factor": k, "exposure": v} for k, v in report.get("factor_exposures", {}).items()])
