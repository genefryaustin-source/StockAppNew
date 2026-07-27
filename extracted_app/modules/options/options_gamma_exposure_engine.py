"""
Sprint 11 Phase 2 — Gamma Exposure Intelligence Engine
"""
from __future__ import annotations
import pandas as pd

def build_gamma_exposure_report(chain_data, underlying_price=None):
    df = chain_data.copy() if isinstance(chain_data, pd.DataFrame) else pd.DataFrame()
    if df.empty:
        return {"available": False, "reason": "No options chain data available."}

    for col in ["gamma","open_interest","strike"]:
        if col not in df.columns:
            df[col] = 0

    spot = float(underlying_price or 1)
    df["gamma_exposure"] = (
        pd.to_numeric(df["gamma"], errors="coerce").fillna(0)
        * pd.to_numeric(df["open_interest"], errors="coerce").fillna(0)
        * 100 * (spot ** 2) * 0.01
    )

    strike_gex = df.groupby("strike", as_index=False).agg(
        gamma_exposure=("gamma_exposure","sum"),
        open_interest=("open_interest","sum")
    ).sort_values("strike")

    strike_gex["cum_gamma"] = strike_gex["gamma_exposure"].cumsum()

    flip = float(strike_gex.iloc[(strike_gex["cum_gamma"].abs()).argmin()]["strike"]) if not strike_gex.empty else spot
    regime = "POSITIVE_GAMMA" if strike_gex["gamma_exposure"].sum() >= 0 else "NEGATIVE_GAMMA"

    return {
        "available": True,
        "summary": {
            "spot": spot,
            "net_gamma": float(strike_gex["gamma_exposure"].sum()),
            "gamma_flip": flip,
            "gamma_regime": regime,
        },
        "strike_gex": strike_gex,
    }

def summarize_gamma_exposure(report):
    if not report.get("available"):
        return report.get("reason","Unavailable")
    s = report["summary"]
    return f"Gamma regime is {s['gamma_regime']} with net gamma {s['net_gamma']:,.0f}. Gamma flip estimated near {s['gamma_flip']}."
