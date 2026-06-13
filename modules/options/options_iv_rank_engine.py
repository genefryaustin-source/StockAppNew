"""IV Rank engine for Phase 4 Options Volatility Suite."""
from __future__ import annotations
from typing import Any


def calculate_iv_rank(surface_report: dict[str, Any]) -> dict[str, Any]:
    s = surface_report.get("summary") or {}
    current = s.get("median_iv")
    low = s.get("min_iv")
    high = s.get("max_iv")
    if current is None or low is None or high is None or high == low:
        return {"iv_rank": None, "label": "Unavailable", "current_iv": current, "low_iv": low, "high_iv": high}
    rank = max(0.0, min(100.0, (float(current) - float(low)) / (float(high) - float(low)) * 100.0))
    if rank >= 80:
        label = "Very High IV"
    elif rank >= 60:
        label = "High IV"
    elif rank <= 20:
        label = "Low IV"
    elif rank <= 40:
        label = "Moderate-Low IV"
    else:
        label = "Normal IV"
    return {"iv_rank": round(rank, 1), "label": label, "current_iv": current, "low_iv": low, "high_iv": high}
