"""IV Percentile proxy engine for Phase 4 Options Volatility Suite."""
from __future__ import annotations
from typing import Any
import pandas as pd
import numpy as np


def calculate_iv_percentile(surface_report: dict[str, Any]) -> dict[str, Any]:
    rows = surface_report.get("surface")

    if rows is None:
        rows = []
    summary = surface_report.get("summary") or {}
    current = summary.get("median_iv")
    rows = surface_report.get("surface")

    if rows is None:
        return {}

    if isinstance(rows, pd.DataFrame):

        if rows.empty:
            return {}

        if "iv" not in rows.columns:
            return {}

        values = (
            pd.to_numeric(rows["iv"], errors="coerce")
            .dropna()
            .tolist()
        )

    else:

        values = [
            float(r["iv"])
            for r in rows
            if isinstance(r, dict) and r.get("iv") is not None
        ]
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
