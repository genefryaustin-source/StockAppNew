
from __future__ import annotations
import pandas as pd

ASSET_BUCKETS = ["Equities","Options","ETF","Futures","Crypto","Fixed Income","Cash"]

def classify_asset(row):
    t = str(row.get("asset_type","Options"))
    return t if t in ASSET_BUCKETS else "Options"

def build_cross_asset_exposure_report(positions):
    df = pd.DataFrame(positions or [])
    if df.empty:
        return {"available":False,"reason":"No positions"}

    if "market_value" not in df.columns:
        df["market_value"] = 0.0

    df["asset_bucket"] = df.apply(classify_asset, axis=1)
    exposure = df.groupby("asset_bucket")["market_value"].sum().reset_index()

    total = max(abs(exposure["market_value"]).sum(),1)
    exposure["exposure_pct"] = exposure["market_value"] / total * 100

    concentration = float(exposure["exposure_pct"].abs().max())

    return {
        "available": True,
        "asset_exposure": exposure,
        "total_exposure": float(total),
        "concentration_score": round(concentration,2),
        "diversification_score": round(max(0,100-concentration),2),
    }

def summarize_cross_asset_exposure(report):
    if not report.get("available"):
        return report.get("reason","Unavailable")
    return (
        f"Cross-asset diversification score "
        f"{report['diversification_score']}/100 with "
        f"concentration score {report['concentration_score']}/100."
    )
