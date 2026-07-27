"""
Sprint 4 Phase 2 — Institutional Flow Cluster Engine.
"""
from __future__ import annotations

from typing import Any
import pandas as pd


def cluster_flow(classification: dict[str, Any]) -> dict[str, Any]:
    if not classification or not classification.get("available"):
        return {"available": False, "reason": (classification or {}).get("reason", "No classification available.")}

    df = classification.get("classified")
    if not isinstance(df, pd.DataFrame) or df.empty:
        return {"available": False, "reason": "No classified rows."}

    df = df.copy()
    for col in ["expiry", "strike", "type", "volume", "premium", "open_interest", "flow_class"]:
        if col not in df.columns:
            df[col] = None

    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)
    df["premium"] = pd.to_numeric(df["premium"], errors="coerce").fillna(0)
    df["open_interest"] = pd.to_numeric(df["open_interest"], errors="coerce").fillna(0)

    by_expiry = (
        df.groupby("expiry", as_index=False)
        .agg(volume=("volume", "sum"), premium=("premium", "sum"), contracts=("expiry", "size"))
        .sort_values("premium", ascending=False)
        .reset_index(drop=True)
    )

    by_strike = (
        df.groupby(["expiry", "strike", "type"], as_index=False)
        .agg(volume=("volume", "sum"), premium=("premium", "sum"), open_interest=("open_interest", "sum"), contracts=("strike", "size"))
        .sort_values("premium", ascending=False)
        .reset_index(drop=True)
    )

    by_class = (
        df.groupby("flow_class", as_index=False)
        .agg(volume=("volume", "sum"), premium=("premium", "sum"), contracts=("flow_class", "size"))
        .sort_values("premium", ascending=False)
        .reset_index(drop=True)
    )

    top_cluster = by_strike.iloc[0].to_dict() if not by_strike.empty else {}

    return {
        "available": True,
        "by_expiry": by_expiry.head(10),
        "by_strike": by_strike.head(20),
        "by_class": by_class,
        "top_cluster": top_cluster,
    }


def summarize_flow_clusters(result: dict[str, Any]) -> str:
    if not result.get("available"):
        return f"Flow clustering unavailable: {result.get('reason', 'unknown reason')}"
    cluster = result.get("top_cluster") or {}
    if not cluster:
        return "No dominant flow cluster detected."
    return (
        f"Top cluster: {cluster.get('type', 'option')} strike {cluster.get('strike')} "
        f"expiring {cluster.get('expiry')} with ${float(cluster.get('premium') or 0):,.0f} premium."
    )
