"""
modules/options/options_positioning_analyzer.py

Phase 3 — Positioning analyzer for institutional options flow.
Identifies strike magnets, expiry magnets, premium concentration, and flow consensus.
"""
from __future__ import annotations

from typing import Any
from collections import defaultdict


def _num(v: Any, default: float = 0.0) -> float:
    try:
        return float(v or default)
    except Exception:
        return default


def _top_group(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    grouped: dict[Any, float] = defaultdict(float)
    counts: dict[Any, int] = defaultdict(int)
    for row in rows:
        k = row.get(key)
        if k is None or k == "":
            continue
        grouped[k] += _num(row.get("premium_est"))
        counts[k] += 1
    if not grouped:
        return {"value": None, "premium": 0.0, "count": 0}
    value, premium = max(grouped.items(), key=lambda x: x[1])
    return {"value": value, "premium": premium, "count": counts[value]}


def analyze_positioning(ticker: str, smart_report: dict[str, Any]) -> dict[str, Any]:
    contracts = smart_report.get("top_contracts") or smart_report.get("flow", {}).get("unusual_contracts") or []
    total_premium = sum(_num(r.get("premium_est")) for r in contracts)
    top_strike = _top_group(contracts, "strike")
    top_expiry = _top_group(contracts, "expiry")

    calls = [r for r in contracts if str(r.get("type", "")).upper() == "CALL"]
    puts = [r for r in contracts if str(r.get("type", "")).upper() == "PUT"]
    call_premium = sum(_num(r.get("premium_est")) for r in calls)
    put_premium = sum(_num(r.get("premium_est")) for r in puts)
    concentration = (top_strike["premium"] / total_premium) if total_premium else 0.0

    if call_premium > put_premium * 1.25:
        consensus = "Call-side positioning"
    elif put_premium > call_premium * 1.25:
        consensus = "Put-side positioning"
    else:
        consensus = "Balanced / two-way positioning"

    if concentration >= 0.45:
        magnet_strength = "Extreme"
    elif concentration >= 0.30:
        magnet_strength = "Strong"
    elif concentration >= 0.18:
        magnet_strength = "Moderate"
    else:
        magnet_strength = "Low"

    return {
        "ticker": ticker.upper(),
        "strike_magnet": top_strike,
        "expiry_magnet": top_expiry,
        "premium_concentration": round(concentration, 4),
        "magnet_strength": magnet_strength,
        "call_premium": call_premium,
        "put_premium": put_premium,
        "consensus": consensus,
        "contract_count": len(contracts),
        "summary": f"{consensus}; strongest strike magnet is {top_strike['value']} with {magnet_strength.lower()} concentration.",
    }
