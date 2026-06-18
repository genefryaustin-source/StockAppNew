"""
Sprint 6 Phase 1 — Execution Quality Intelligence Engine.

Institutional execution analytics for options orders:
- Fill quality
- Midpoint capture
- Slippage
- Spread paid
- Price improvement
- Execution grade
- Broker/paper/live comparison
- Order-level diagnostics
"""
from __future__ import annotations

from typing import Any
import pandas as pd


def _as_orders_frame(orders: Any) -> pd.DataFrame:
    if orders is None:
        return pd.DataFrame()
    if isinstance(orders, pd.DataFrame):
        return orders.copy()
    if isinstance(orders, list):
        return pd.DataFrame(orders)
    return pd.DataFrame()


def _num(series: pd.Series, default: float = 0.0) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(default)


def normalize_execution_orders(orders: Any) -> pd.DataFrame:
    df = _as_orders_frame(orders)
    if df.empty:
        return df

    df = df.copy()

    defaults = {
        "created_at": "",
        "symbol": "",
        "option_symbol": "",
        "underlying": "",
        "side": "",
        "qty": 0,
        "quantity": 0,
        "limit_price": 0,
        "submitted_price": 0,
        "filled_price": 0,
        "fill_price": 0,
        "avg_fill_price": 0,
        "bid": 0,
        "ask": 0,
        "mid": 0,
        "status": "",
        "order_status": "",
        "mode": "",
        "paper": None,
        "broker": "",
        "strategy": "",
    }

    for col, default in defaults.items():
        if col not in df.columns:
            df[col] = default

    df["side"] = df["side"].fillna("").astype(str).str.lower()
    df["status"] = (
        df["status"]
        .fillna("")
        .astype(str)
        .replace("", pd.NA)
        .fillna(df["order_status"].fillna("").astype(str))
        .fillna("")
        .astype(str)
        .str.lower()
    )

    df["qty"] = _num(df["qty"]).where(_num(df["qty"]) != 0, _num(df["quantity"]))

    for col in [
        "limit_price",
        "submitted_price",
        "filled_price",
        "fill_price",
        "avg_fill_price",
        "bid",
        "ask",
        "mid",
    ]:
        df[col] = _num(df[col])

    df["execution_price"] = (
        df["filled_price"]
        .where(df["filled_price"] > 0, df["fill_price"])
        .where(lambda s: s > 0, df["avg_fill_price"])
    )

    df["reference_price"] = (
        df["limit_price"]
        .where(df["limit_price"] > 0, df["submitted_price"])
    )

    df["computed_mid"] = ((df["bid"] + df["ask"]) / 2).where((df["bid"] > 0) & (df["ask"] > 0), df["mid"])
    df["spread"] = (df["ask"] - df["bid"]).where((df["ask"] > 0) & (df["bid"] > 0), 0)
    df["spread_pct"] = (df["spread"] / df["computed_mid"].replace(0, 1)).clip(lower=0)

    df["is_filled"] = df["status"].str.contains("fill|filled|executed|done", case=False, regex=True)
    df["is_buy"] = df["side"].str.contains("buy|bto|btc", case=False, regex=True)
    df["is_sell"] = df["side"].str.contains("sell|sto|stc", case=False, regex=True)

    return df


def calculate_order_execution_quality(row: pd.Series) -> dict[str, Any]:
    filled = bool(row.get("is_filled"))
    side_buy = bool(row.get("is_buy"))
    side_sell = bool(row.get("is_sell"))

    execution = float(row.get("execution_price") or 0)
    reference = float(row.get("reference_price") or 0)
    mid = float(row.get("computed_mid") or 0)
    bid = float(row.get("bid") or 0)
    ask = float(row.get("ask") or 0)
    spread = max(0.0, float(row.get("spread") or 0))

    if not filled or execution <= 0:
        return {
            "fill_quality": "UNFILLED",
            "execution_score": 0.0,
            "slippage": 0.0,
            "slippage_bps": 0.0,
            "midpoint_capture_pct": 0.0,
            "spread_paid_pct": 0.0,
            "price_improvement": 0.0,
            "diagnostic": "Order not filled or missing execution price.",
        }

    if reference <= 0:
        reference = mid if mid > 0 else execution

    if side_buy:
        slippage = execution - reference
        midpoint_edge = mid - execution if mid > 0 else 0
        spread_paid = execution - bid if bid > 0 else 0
    elif side_sell:
        slippage = reference - execution
        midpoint_edge = execution - mid if mid > 0 else 0
        spread_paid = ask - execution if ask > 0 else 0
    else:
        slippage = abs(execution - reference)
        midpoint_edge = 0
        spread_paid = 0

    slippage_bps = (slippage / max(0.01, reference)) * 10000
    spread_paid_pct = (spread_paid / max(0.01, spread)) * 100 if spread > 0 else 0
    midpoint_capture_pct = (midpoint_edge / max(0.01, spread / 2)) * 100 if spread > 0 else 0
    price_improvement = -slippage

    score = 75.0

    if slippage_bps <= 0:
        score += 15
    elif slippage_bps <= 25:
        score += 5
    elif slippage_bps <= 100:
        score -= 10
    elif slippage_bps <= 250:
        score -= 25
    else:
        score -= 40

    if spread > 0:
        if spread_paid_pct <= 25:
            score += 10
        elif spread_paid_pct <= 50:
            score += 3
        elif spread_paid_pct >= 80:
            score -= 15

        if midpoint_capture_pct >= 50:
            score += 10
        elif midpoint_capture_pct < 0:
            score -= 10

    score = round(max(0, min(100, score)), 2)

    if score >= 85:
        quality = "EXCELLENT"
    elif score >= 70:
        quality = "GOOD"
    elif score >= 50:
        quality = "FAIR"
    elif score > 0:
        quality = "POOR"
    else:
        quality = "UNFILLED"

    diagnostic = (
        f"Execution score {score}/100. "
        f"Slippage {slippage_bps:.1f} bps. "
        f"Spread paid {spread_paid_pct:.1f}%."
    )

    return {
        "fill_quality": quality,
        "execution_score": score,
        "slippage": round(slippage, 4),
        "slippage_bps": round(slippage_bps, 2),
        "midpoint_capture_pct": round(midpoint_capture_pct, 2),
        "spread_paid_pct": round(spread_paid_pct, 2),
        "price_improvement": round(price_improvement, 4),
        "diagnostic": diagnostic,
    }


def analyze_execution_quality(orders: Any) -> dict[str, Any]:
    df = normalize_execution_orders(orders)
    if df.empty:
        return {"available": False, "reason": "No order history available.", "orders": df}

    quality = pd.DataFrame([calculate_order_execution_quality(row) for _, row in df.iterrows()])
    enriched = pd.concat([df.reset_index(drop=True), quality.reset_index(drop=True)], axis=1)

    filled = enriched[enriched["is_filled"]].copy()
    fill_rate = round(float(len(filled) / max(1, len(enriched)) * 100), 2)

    avg_score = round(float(filled["execution_score"].mean()), 2) if not filled.empty else 0.0
    avg_slippage_bps = round(float(filled["slippage_bps"].mean()), 2) if not filled.empty else 0.0
    avg_spread_paid = round(float(filled["spread_paid_pct"].mean()), 2) if not filled.empty else 0.0
    avg_mid_capture = round(float(filled["midpoint_capture_pct"].mean()), 2) if not filled.empty else 0.0

    if avg_score >= 85:
        grade = "A"
    elif avg_score >= 70:
        grade = "B"
    elif avg_score >= 55:
        grade = "C"
    elif avg_score > 0:
        grade = "D"
    else:
        grade = "UNRATED"

    return {
        "available": True,
        "orders": enriched,
        "filled_orders": filled,
        "summary": {
            "order_count": int(len(enriched)),
            "filled_count": int(len(filled)),
            "fill_rate": fill_rate,
            "avg_execution_score": avg_score,
            "execution_grade": grade,
            "avg_slippage_bps": avg_slippage_bps,
            "avg_spread_paid_pct": avg_spread_paid,
            "avg_midpoint_capture_pct": avg_mid_capture,
        },
    }


def analyze_execution_by_group(orders: Any, group_col: str) -> dict[str, Any]:
    report = analyze_execution_quality(orders)
    if not report.get("available"):
        return report

    df = report.get("orders")
    if not isinstance(df, pd.DataFrame) or df.empty:
        return {"available": False, "reason": "No enriched orders available."}

    if group_col not in df.columns:
        df[group_col] = "Unknown"

    grouped = (
        df.groupby(group_col, as_index=False)
        .agg(
            orders=(group_col, "size"),
            filled=("is_filled", "sum"),
            avg_score=("execution_score", "mean"),
            avg_slippage_bps=("slippage_bps", "mean"),
            avg_spread_paid_pct=("spread_paid_pct", "mean"),
            avg_midpoint_capture_pct=("midpoint_capture_pct", "mean"),
        )
        .reset_index(drop=True)
    )

    grouped["fill_rate"] = (grouped["filled"] / grouped["orders"].replace(0, 1) * 100).round(2)

    for col in ["avg_score", "avg_slippage_bps", "avg_spread_paid_pct", "avg_midpoint_capture_pct"]:
        grouped[col] = pd.to_numeric(grouped[col], errors="coerce").fillna(0).round(2)

    return {"available": True, "group": group_col, "table": grouped}


def build_execution_quality_report(orders: Any) -> dict[str, Any]:
    report = analyze_execution_quality(orders)
    if not report.get("available"):
        return report

    orders_df = report.get("orders")

    return {
        **report,
        "by_symbol": analyze_execution_by_group(orders_df, "underlying"),
        "by_strategy": analyze_execution_by_group(orders_df, "strategy"),
        "by_mode": analyze_execution_by_group(orders_df, "mode"),
        "by_broker": analyze_execution_by_group(orders_df, "broker"),
    }


def summarize_execution_quality(report: dict[str, Any]) -> str:
    if not report.get("available"):
        return f"Execution quality unavailable: {report.get('reason', 'unknown reason')}"

    summary = report.get("summary", {})

    return (
        f"Execution grade {summary.get('execution_grade')} with average score "
        f"{summary.get('avg_execution_score')}/100. Fill rate "
        f"{summary.get('fill_rate')}%, average slippage "
        f"{summary.get('avg_slippage_bps')} bps, and average spread paid "
        f"{summary.get('avg_spread_paid_pct')}%."
    )
