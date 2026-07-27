"""
modules/options/options_gamma_exposure_engine.py

Sprint 11 Phase 2 — Gamma Exposure Intelligence Engine

CHANGES:
- Fixed: _as_frame() previously checked isinstance(chain_data, pd.DataFrame),
  but chain_data is always a dict here (the documented, universal shape used
  throughout this app: {ticker, chain, expirations, all_rows, ...} -- see
  options_data_service.py). That check could never be true, so df was always
  empty and the entire "Gamma Exposure" workspace always reported "no data
  available" regardless of how much real chain data was actually passed in.
  Confirmed directly with a real, valid chain_data sample before fixing.
  Now extracts chain_data["all_rows"], the same pattern already working
  correctly in options_max_pain_engine.py.
- Fixed: build_gamma_exposure_report() never actually sourced underlying_price
  from chain_data itself, and the dashboard that calls it
  (options_gamma_exposure_dashboard.py) never passes one explicitly either --
  so spot silently defaulted to 1, making every gamma exposure number wrong
  by a factor of the real spot price squared (the formula scales by
  spot ** 2). Now falls back to chain_data["underlying_price"] (the same key
  options_max_pain_engine.py reads) before defaulting.
- Both fixes verified against hand-calculated expected values, not just
  "no longer crashes/returns available: False".
"""
from __future__ import annotations
import pandas as pd


def _as_frame(chain_data) -> pd.DataFrame:
    """
    chain_data is always a dict here (the documented, universal shape
    used throughout this app: {ticker, chain, expirations, all_rows,
    ...} -- see options_data_service.py), never a raw DataFrame.
    Matches the same extraction already used correctly in
    options_max_pain_engine.py.
    """
    if not chain_data:
        return pd.DataFrame()
    rows = chain_data.get("all_rows") if isinstance(chain_data, dict) else None
    if isinstance(rows, pd.DataFrame):
        return rows.copy()
    if isinstance(rows, list):
        return pd.DataFrame(rows)
    return pd.DataFrame()


def build_gamma_exposure_report(chain_data, underlying_price=None):
    df = _as_frame(chain_data)
    if df.empty:
        return {"available": False, "reason": "No options chain data available."}

    for col in ["gamma","open_interest","strike"]:
        if col not in df.columns:
            df[col] = 0

    # underlying_price was never actually being sourced from chain_data
    # itself -- confirmed the dashboard never passes it explicitly,
    # silently defaulting spot to 1 and making every gamma exposure
    # number wrong by a factor of the real spot price squared. Falls
    # back to chain_data's own underlying_price (the same key
    # options_max_pain_engine.py reads) before defaulting.
    if underlying_price is None and isinstance(chain_data, dict):
        underlying_price = chain_data.get("underlying_price")
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