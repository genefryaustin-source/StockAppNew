
from __future__ import annotations
import pandas as pd

DEFAULT_COVERED_CALL_POLICY = {
    "min_shares": 100,
    "target_delta_min": 0.15,
    "target_delta_max": 0.35,
    "min_annualized_yield": 8.0,
}

def build_covered_call_candidates(positions, chain_data=None, policy=None):
    policy = policy or DEFAULT_COVERED_CALL_POLICY

    if positions is None:
        positions = []

    df = pd.DataFrame(positions)

    if df.empty:
        return {
            "available": False,
            "reason": "No positions available."
        }

    if "shares" not in df.columns:
        df["shares"] = 0

    if "underlying" not in df.columns:
        df["underlying"] = ""

    candidates = []

    for _, row in df.iterrows():

        shares = float(row.get("shares", 0) or 0)

        if shares < policy["min_shares"]:
            continue

        underlying = str(row.get("underlying", ""))

        contracts = int(shares // 100)

        candidates.append({
            "Underlying": underlying,
            "Shares": shares,
            "Contracts Available": contracts,
            "Suggested Delta": "0.20-0.30",
            "Estimated Annual Yield %": 10.0,
            "Assignment Risk": "Moderate",
            "Action": "Sell Covered Call"
        })

    candidates_df = pd.DataFrame(candidates)

    return {
        "available": True,
        "candidate_count": len(candidates_df),
        "candidates": candidates_df
    }

def summarize_covered_call_factory(report):
    if not report.get("available"):
        return report.get("reason", "Unavailable")

    return (
        f"{report.get('candidate_count',0)} covered call "
        f"opportunities identified."
    )
