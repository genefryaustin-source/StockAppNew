"""Event-pricing strategy selection for Phase 4."""
from __future__ import annotations
from typing import Any


def classify_event_pricing(iv_rank: dict[str, Any], iv_percentile: dict[str, Any], earnings: dict[str, Any], term: dict[str, Any], skew: dict[str, Any]) -> dict[str, Any]:
    rank = iv_rank.get("iv_rank")
    pct = iv_percentile.get("iv_percentile")
    crush_pct = earnings.get("vol_crush_pct") or 0
    slope = term.get("slope") or 0
    rr = skew.get("risk_reversal") or 0

    expensive = (rank is not None and rank >= 65) or (pct is not None and pct >= 70)
    cheap = (rank is not None and rank <= 35) or (pct is not None and pct <= 30)

    if expensive and crush_pct > 0.15:
        label = "Earnings Premium Overpriced"
        strategies = ["Iron Condor", "Short Strangle", "Calendar Spread", "Credit Spreads"]
    elif cheap:
        label = "Earnings Premium Underpriced"
        strategies = ["Long Straddle", "Long Strangle", "Debit Spread"]
    elif slope < -0.03:
        label = "Event Premium Concentrated Front-Month"
        strategies = ["Calendar Spread", "Diagonal Spread"]
    elif rr < -0.03:
        label = "Downside Hedge Demand"
        strategies = ["Put Spread", "Collar", "Protective Put"]
    elif rr > 0.03:
        label = "Upside Call Demand"
        strategies = ["Call Spread", "Ratio Call Spread"]
    else:
        label = "Balanced Event Pricing"
        strategies = ["Defined-Risk Spread", "Wait for Better Mispricing"]

    return {
        "label": label,
        "recommended_strategies": strategies,
        "is_expensive": expensive,
        "is_cheap": cheap,
        "inputs": {
            "iv_rank": rank,
            "iv_percentile": pct,
            "crush_pct": crush_pct,
            "term_slope": slope,
            "risk_reversal": rr,
        },
    }
