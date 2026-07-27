"""Options skew analysis for Phase 4."""
from __future__ import annotations
from typing import Any
import pandas as pd


def analyze_skew(surface_report: dict[str, Any], spot: float | None = None) -> dict[str, Any]:
    rows = surface_report.get("surface")

    if rows is None:
        return {"error": "No surface rows for skew analysis"}

    # Support both DataFrame and legacy list-of-dicts
    if isinstance(rows, pd.DataFrame):
        df = rows.copy()
    else:
        df = pd.DataFrame(rows)

    if df.empty:
        return {"error": "No surface rows for skew analysis"}

    required = {"iv", "strike"}
    missing = required - set(df.columns)
    if missing:
        return {"error": f"Missing required columns: {', '.join(sorted(missing))}"}

    df["iv"] = pd.to_numeric(df["iv"], errors="coerce")
    df["strike"] = pd.to_numeric(df["strike"], errors="coerce")

    df = df.dropna(subset=["iv", "strike"])

    if df.empty:
        return {"error": "No valid IV rows after cleaning"}
    calls = df[df["type"].astype(str).str.lower() == "call"]
    puts = df[df["type"].astype(str).str.lower() == "put"]
    call_iv = float(calls["iv"].median()) if not calls.empty else 0.0
    put_iv = float(puts["iv"].median()) if not puts.empty else 0.0
    risk_reversal = call_iv - put_iv
    if risk_reversal > 0.03:
        label = "Call Skew / Upside Demand"
    elif risk_reversal < -0.03:
        label = "Put Skew / Downside Protection"
    else:
        label = "Balanced Skew"

    strike_skew = []
    if spot:
        df["moneyness"] = df["strike"] / float(spot)
        buckets = [("Deep Put Wing", 0, 0.90), ("Put Wing", 0.90, 0.98), ("ATM", 0.98, 1.02), ("Call Wing", 1.02, 1.10), ("Deep Call Wing", 1.10, 999)]
        for name, lo, hi in buckets:
            b = df[(df["moneyness"] >= lo) & (df["moneyness"] < hi)]
            if not b.empty:
                strike_skew.append({"bucket": name, "median_iv": float(b["iv"].median()), "contracts": int(len(b))})

    return {
        "call_skew": call_iv,
        "put_skew": put_iv,
        "risk_reversal": risk_reversal,
        "label": label,
        "strike_skew": strike_skew,
    }
