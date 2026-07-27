"""Trade outcome analytics for Phase 8."""
from __future__ import annotations
from typing import Any
import math
import pandas as pd


def outcome_frame(records: list[dict[str, Any]]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    for col in ["pnl", "return_pct", "entry_price", "exit_price", "qty"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


def analyze_trade_outcomes(records: list[dict[str, Any]]) -> dict[str, Any]:
    df = outcome_frame(records)
    if df.empty:
        return {"trade_count": 0, "win_rate": 0, "total_pnl": 0, "avg_return_pct": 0, "profit_factor": 0, "best_trade": None, "worst_trade": None}
    wins = df[df["pnl"] > 0]
    losses = df[df["pnl"] < 0]
    gross_profit = float(wins["pnl"].sum()) if not wins.empty else 0.0
    gross_loss = abs(float(losses["pnl"].sum())) if not losses.empty else 0.0
    best = df.sort_values("pnl", ascending=False).head(1).to_dict("records")[0]
    worst = df.sort_values("pnl", ascending=True).head(1).to_dict("records")[0]
    return {
        "trade_count": int(len(df)),
        "win_rate": round(len(wins) / max(1, len(df)) * 100, 1),
        "total_pnl": round(float(df["pnl"].sum()), 2),
        "avg_return_pct": round(float(df["return_pct"].mean()), 2),
        "median_return_pct": round(float(df["return_pct"].median()), 2),
        "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss else (round(gross_profit, 2) if gross_profit else 0),
        "avg_win": round(float(wins["pnl"].mean()), 2) if not wins.empty else 0,
        "avg_loss": round(float(losses["pnl"].mean()), 2) if not losses.empty else 0,
        "best_trade": best,
        "worst_trade": worst,
    }


def equity_curve(records: list[dict[str, Any]]) -> pd.DataFrame:
    df = outcome_frame(records)
    if df.empty:
        return pd.DataFrame()
    if "created_at" in df.columns:
        df = df.sort_values("created_at")
    df["cumulative_pnl"] = df["pnl"].cumsum()
    df["trade_number"] = range(1, len(df) + 1)
    return df[["trade_number", "created_at", "strategy", "pnl", "cumulative_pnl"]]
