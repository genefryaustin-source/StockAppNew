"""Strategy attribution analytics for options performance learning."""
from __future__ import annotations
from typing import Any
import pandas as pd


def strategy_attribution(records: list[dict[str, Any]]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    if df.empty or "strategy" not in df.columns:
        return pd.DataFrame()
    df["pnl"] = pd.to_numeric(df.get("pnl", 0), errors="coerce").fillna(0)
    df["return_pct"] = pd.to_numeric(df.get("return_pct", 0), errors="coerce").fillna(0)
    grouped = df.groupby("strategy", dropna=False).agg(
        trades=("strategy", "count"),
        total_pnl=("pnl", "sum"),
        avg_pnl=("pnl", "mean"),
        avg_return_pct=("return_pct", "mean"),
        wins=("pnl", lambda s: int((s > 0).sum())),
        losses=("pnl", lambda s: int((s < 0).sum())),
    ).reset_index()
    grouped["win_rate"] = (grouped["wins"] / grouped["trades"].clip(lower=1) * 100).round(1)
    return grouped.sort_values(["total_pnl", "win_rate"], ascending=False).round(2)


def tag_attribution(records: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for rec in records or []:
        for tag in rec.get("tags") or ["untagged"]:
            rows.append({"tag": tag, "pnl": rec.get("pnl", 0), "return_pct": rec.get("return_pct", 0)})
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["pnl"] = pd.to_numeric(df["pnl"], errors="coerce").fillna(0)
    df["return_pct"] = pd.to_numeric(df["return_pct"], errors="coerce").fillna(0)
    out = df.groupby("tag").agg(trades=("tag", "count"), total_pnl=("pnl", "sum"), avg_return_pct=("return_pct", "mean")).reset_index()
    return out.sort_values("total_pnl", ascending=False).round(2)
