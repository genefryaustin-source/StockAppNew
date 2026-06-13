"""IV Percentile proxy engine for Phase 4 Options Volatility Suite."""
from __future__ import annotations
from typing import Any


def calculate_iv_percentile(surface_report: dict[str, Any]) -> dict[str, Any]:
    rows = surface_report.get("surface") or []
    summary = surface_report.get("summary") or {}
    current = summary.get("median_iv")
    values = [float(r.get("iv")) for r in rows if r.get("iv") is not None]
    if current is None or not values:
        return {"iv_percentile": None, "label": "Unavailable"}
    below = sum(1 for v in values if v <= float(current))
    pct = below / max(1, len(values)) * 100.0
    if pct >= 80:
        label = "Premium Rich"
    elif pct >= 60:
        label = "Elevated"
    elif pct <= 20:
        label = "Premium Cheap"
    elif pct <= 40:
        label = "Below Normal"
    else:
        label = "Balanced"
    return {"iv_percentile": round(pct, 1), "label": label, "sample_size": len(values)}
