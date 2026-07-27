"""Volatility term structure analytics for Phase 4."""
from __future__ import annotations
from typing import Any


def analyze_term_structure(surface_report: dict[str, Any]) -> dict[str, Any]:
    points = sorted(surface_report.get("term_points") or [], key=lambda r: float(r.get("dte") or 0))
    if len(points) < 2:
        return {"error": "Not enough expirations for term structure", "points": points}
    front = points[0]
    back = points[-1]
    front_iv = float(front.get("median_iv") or 0)
    back_iv = float(back.get("median_iv") or 0)
    slope = back_iv - front_iv
    slope_pct = slope / front_iv if front_iv else 0.0
    if slope < -0.03:
        regime = "Backwardation / Event Premium"
    elif slope > 0.03:
        regime = "Contango / Normal Carry"
    else:
        regime = "Flat Term Structure"
    return {
        "front_dte": int(front.get("dte") or 0),
        "front_iv": front_iv,
        "back_dte": int(back.get("dte") or 0),
        "back_iv": back_iv,
        "slope": slope,
        "slope_pct": slope_pct,
        "regime": regime,
        "points": points,
    }
