"""
Sprint 8 Phase 3 — Income Generation Intelligence Engine
"""

from __future__ import annotations

from typing import Any
import pandas as pd


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def normalize_income_positions(positions) -> pd.DataFrame:
    if positions is None:
        return pd.DataFrame()

    if isinstance(positions, pd.DataFrame):
        df = positions.copy()
    else:
        df = pd.DataFrame(positions)

    if df.empty:
        return df

    defaults = {
        "symbol": "",
        "strategy": "",
        "premium": 0,
        "qty": 0,
        "market_value": 0,
        "unrealized_pnl": 0,
        "dte": 0,
        "iv": 0,
    }

    for col, val in defaults.items():
        if col not in df.columns:
            df[col] = val

    return df


def calculate_premium_capture(df: pd.DataFrame) -> dict:
    if df.empty:
        return {}

    total_premium = (
        pd.to_numeric(df["premium"], errors="coerce")
        .fillna(0)
        .sum()
    )

    return {
        "total_premium": round(float(total_premium), 2),
        "monthly_income": round(float(total_premium) / 12, 2),
        "quarterly_income": round(float(total_premium) / 4, 2),
        "annual_income": round(float(total_premium), 2),
    }


def calculate_income_yield(df: pd.DataFrame) -> dict:
    if df.empty:
        return {}

    premium = (
        pd.to_numeric(df["premium"], errors="coerce")
        .fillna(0)
        .sum()
    )

    capital = (
        pd.to_numeric(df["market_value"], errors="coerce")
        .fillna(0)
        .abs()
        .sum()
    )

    if capital <= 0:
        capital = 1

    monthly_yield = (premium / capital) * 100
    annualized_yield = monthly_yield * 12

    return {
        "capital": round(capital, 2),
        "monthly_yield": round(monthly_yield, 2),
        "annualized_yield": round(annualized_yield, 2),
    }


def analyze_wheel_performance(df: pd.DataFrame) -> dict:
    if df.empty:
        return {}

    strategies = (
        df["strategy"]
        .fillna("")
        .astype(str)
        .str.lower()
    )

    wheel = df[
        strategies.str.contains("wheel")
        | strategies.str.contains("covered")
        | strategies.str.contains("cash")
    ]

    premium = (
        pd.to_numeric(
            wheel.get("premium", 0),
            errors="coerce"
        )
        .fillna(0)
        .sum()
    )

    return {
        "wheel_positions": len(wheel),
        "wheel_income": round(float(premium), 2),
    }


def forecast_income_generation(df: pd.DataFrame) -> dict:
    if df.empty:
        return {}

    premium = (
        pd.to_numeric(df["premium"], errors="coerce")
        .fillna(0)
        .sum()
    )

    monthly = premium / 12

    return {
        "30_day": round(monthly, 2),
        "60_day": round(monthly * 2, 2),
        "90_day": round(monthly * 3, 2),
        "annual_projection": round(monthly * 12, 2),
    }


def identify_income_opportunities(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    work = df.copy()

    if "iv" in work.columns:
        work["Income Score"] = (
            pd.to_numeric(
                work["iv"],
                errors="coerce"
            ).fillna(0)
        )
    else:
        work["Income Score"] = 0

    work = work.sort_values(
        "Income Score",
        ascending=False
    )

    return work.head(25)


def build_income_intelligence_report(
    positions,
    transactions=None,
):
    df = normalize_income_positions(positions)

    if df.empty:
        return {
            "available": False,
            "reason": "No positions found.",
        }

    premium = calculate_premium_capture(df)
    yield_data = calculate_income_yield(df)
    wheel = analyze_wheel_performance(df)
    forecast = forecast_income_generation(df)
    opportunities = identify_income_opportunities(df)

    return {
        "available": True,
        "summary": {
            **premium,
            **yield_data,
            **wheel,
        },
        "forecast": forecast,
        "opportunities": opportunities,
        "positions": df,
    }


def summarize_income_intelligence(report: dict) -> str:
    if not report.get("available"):
        return report.get("reason", "Unavailable")

    s = report["summary"]

    return (
        f"Premium income ${s.get('total_premium',0):,.0f}. "
        f"Annualized yield {s.get('annualized_yield',0):.1f}%. "
        f"Wheel income ${s.get('wheel_income',0):,.0f}."
    )