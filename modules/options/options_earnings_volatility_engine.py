"""Earnings volatility intelligence for Phase 4."""
from __future__ import annotations
from typing import Any
import math


def estimate_earnings_volatility(surface_report: dict[str, Any], spot: float, days_to_event: int = 7) -> dict[str, Any]:
    summary = surface_report.get("summary") or {}
    term_points = sorted(surface_report.get("term_points") or [], key=lambda r: float(r.get("dte") or 0))
    median_iv = float(summary.get("median_iv") or 0)
    front_iv = float(term_points[0].get("median_iv") or median_iv) if term_points else median_iv
    back_iv = float(term_points[-1].get("median_iv") or median_iv) if term_points else median_iv
    event_iv = max(front_iv, median_iv)
    expected_move = float(spot or 0) * event_iv * math.sqrt(max(days_to_event, 1) / 365.0)
    crush = max(0.0, front_iv - back_iv)
    crush_pct = crush / front_iv if front_iv else 0.0
    if crush_pct >= 0.25:
        crush_label = "High Crush Risk"
    elif crush_pct >= 0.12:
        crush_label = "Moderate Crush Risk"
    else:
        crush_label = "Low Crush Risk"
    return {
        "days_to_event": days_to_event,
        "event_iv": event_iv,
        "expected_earnings_move": expected_move,
        "expected_move_pct": expected_move / spot if spot else None,
        "front_iv": front_iv,
        "back_iv": back_iv,
        "vol_crush_estimate": crush,
        "vol_crush_pct": crush_pct,
        "vol_crush_label": crush_label,
    }
