"""
Sprint 5 Phase 5 — Portfolio Construction Intelligence Engine.

Institutional portfolio construction analytics for options portfolios:
- Strategy mix analysis
- Capital allocation by strategy / underlying / expiry
- Risk-budget allocation
- Diversification diagnostics
- Rebalancing recommendations
- Portfolio construction score

Works with normalized positions from:
modules.options.options_portfolio_risk_engine.normalize_risk_positions
"""
from __future__ import annotations

from typing import Any
import pandas as pd

from modules.options.options_portfolio_risk_engine import normalize_risk_positions


DEFAULT_TARGETS = {
    "max_underlying_share": 35.0,
    "max_expiry_share": 40.0,
    "max_strategy_share": 45.0,
    "min_strategy_count": 2,
    "target_income_share": 35.0,
    "target_directional_share": 35.0,
    "target_volatility_share": 20.0,
    "target_hedge_share": 10.0,
}


def _empty(reason: str) -> dict[str, Any]:
    return {"available": False, "reason": reason}


def _num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0)


def _classify_strategy_bucket(row: pd.Series) -> str:
    strategy = str(row.get("strategy") or "").lower()
    opt_type = str(row.get("option_type") or row.get("type") or "").lower()
    qty = float(row.get("qty") or 0)

    if any(x in strategy for x in ["covered", "cash secured", "credit", "income", "condor", "short premium"]):
        return "Income"

    if any(x in strategy for x in ["straddle", "strangle", "calendar", "diagonal", "volatility", "long vol"]):
        return "Volatility"

    if any(x in strategy for x in ["hedge", "protective", "collar"]):
        return "Hedge"

    if opt_type in {"put", "call"}:
        if qty < 0:
            return "Income"
        return "Directional"

    return "Unclassified"


def _allocation_table(df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    if group_col not in df.columns:
        df[group_col] = "Unknown"

    total_notional = max(1.0, float(df["notional_proxy"].abs().sum() or df["abs_market_value"].sum() or 1.0))

    table = (
        df.groupby(group_col, as_index=False)
        .agg(
            positions=(group_col, "size"),
            market_value=("market_value", "sum"),
            abs_market_value=("abs_market_value", "sum"),
            notional_proxy=("notional_proxy", "sum"),
            net_delta=("net_delta", "sum"),
            net_gamma=("net_gamma", "sum"),
            net_theta=("net_theta", "sum"),
            net_vega=("net_vega", "sum"),
        )
        .sort_values("notional_proxy", ascending=False)
        .reset_index(drop=True)
    )

    table["allocation_pct"] = (table["notional_proxy"].abs() / total_notional * 100).round(2)

    for col in [
        "market_value",
        "abs_market_value",
        "notional_proxy",
        "net_delta",
        "net_gamma",
        "net_theta",
        "net_vega",
    ]:
        if col in table.columns:
            table[col] = _num(table[col]).round(4)

    return table


def analyze_strategy_mix(positions: Any) -> dict[str, Any]:
    df = normalize_risk_positions(positions)
    if df.empty:
        return _empty("No positions available.")

    df = df.copy()
    if "strategy" not in df.columns:
        df["strategy"] = "Unclassified"

    df["strategy"] = df["strategy"].fillna("Unclassified").replace("", "Unclassified")
    df["strategy_bucket"] = df.apply(_classify_strategy_bucket, axis=1)

    by_strategy = _allocation_table(df, "strategy")
    by_bucket = _allocation_table(df, "strategy_bucket")

    return {
        "available": True,
        "by_strategy": by_strategy,
        "by_bucket": by_bucket,
        "strategy_count": int(df["strategy"].nunique()),
        "bucket_count": int(df["strategy_bucket"].nunique()),
    }


def analyze_capital_allocation(positions: Any) -> dict[str, Any]:
    df = normalize_risk_positions(positions)
    if df.empty:
        return _empty("No positions available.")

    df = df.copy()
    if "strategy" not in df.columns:
        df["strategy"] = "Unclassified"
    df["strategy"] = df["strategy"].fillna("Unclassified").replace("", "Unclassified")
    df["strategy_bucket"] = df.apply(_classify_strategy_bucket, axis=1)

    return {
        "available": True,
        "by_underlying": _allocation_table(df, "underlying"),
        "by_expiry": _allocation_table(df, "expiry"),
        "by_strategy_bucket": _allocation_table(df, "strategy_bucket"),
        "by_strategy": _allocation_table(df, "strategy"),
        "gross_notional_proxy": round(float(df["notional_proxy"].abs().sum()), 2),
        "net_market_value": round(float(df["market_value"].sum()), 2),
    }


def calculate_risk_budget(positions: Any) -> dict[str, Any]:
    df = normalize_risk_positions(positions)
    if df.empty:
        return _empty("No positions available.")

    df = df.copy()
    if "strategy" not in df.columns:
        df["strategy"] = "Unclassified"
    df["strategy"] = df["strategy"].fillna("Unclassified").replace("", "Unclassified")
    df["strategy_bucket"] = df.apply(_classify_strategy_bucket, axis=1)

    df["risk_budget"] = (
        df["net_delta"].abs() * 0.25
        + df["net_gamma"].abs() * 0.30
        + df["net_vega"].abs() * 0.25
        + df["net_theta"].abs() * 0.10
        + df["notional_proxy"].abs() * 0.10
    )

    total_risk = max(1.0, float(df["risk_budget"].sum() or 1.0))

    risk_by_bucket = (
        df.groupby("strategy_bucket", as_index=False)
        .agg(
            risk_budget=("risk_budget", "sum"),
            positions=("strategy_bucket", "size"),
            notional_proxy=("notional_proxy", "sum"),
            net_delta=("net_delta", "sum"),
            net_gamma=("net_gamma", "sum"),
            net_theta=("net_theta", "sum"),
            net_vega=("net_vega", "sum"),
        )
        .sort_values("risk_budget", ascending=False)
        .reset_index(drop=True)
    )
    risk_by_bucket["risk_budget_pct"] = (risk_by_bucket["risk_budget"] / total_risk * 100).round(2)

    risk_by_underlying = (
        df.groupby("underlying", as_index=False)
        .agg(
            risk_budget=("risk_budget", "sum"),
            positions=("underlying", "size"),
            notional_proxy=("notional_proxy", "sum"),
            net_delta=("net_delta", "sum"),
            net_gamma=("net_gamma", "sum"),
            net_theta=("net_theta", "sum"),
            net_vega=("net_vega", "sum"),
        )
        .sort_values("risk_budget", ascending=False)
        .reset_index(drop=True)
    )
    risk_by_underlying["risk_budget_pct"] = (risk_by_underlying["risk_budget"] / total_risk * 100).round(2)

    return {
        "available": True,
        "total_risk_budget": round(total_risk, 4),
        "risk_by_bucket": risk_by_bucket,
        "risk_by_underlying": risk_by_underlying,
    }


def diagnose_diversification(positions: Any, targets: dict[str, float] | None = None) -> dict[str, Any]:
    targets = targets or DEFAULT_TARGETS
    df = normalize_risk_positions(positions)
    if df.empty:
        return _empty("No positions available.")

    strategy_mix = analyze_strategy_mix(df)
    allocation = analyze_capital_allocation(df)

    issues = []
    score = 100.0

    by_underlying = allocation.get("by_underlying")
    by_expiry = allocation.get("by_expiry")
    by_strategy = allocation.get("by_strategy")
    by_bucket = strategy_mix.get("by_bucket")

    max_underlying = float(by_underlying["allocation_pct"].max()) if isinstance(by_underlying, pd.DataFrame) and not by_underlying.empty else 0
    max_expiry = float(by_expiry["allocation_pct"].max()) if isinstance(by_expiry, pd.DataFrame) and not by_expiry.empty else 0
    max_strategy = float(by_strategy["allocation_pct"].max()) if isinstance(by_strategy, pd.DataFrame) and not by_strategy.empty else 0

    if max_underlying > targets["max_underlying_share"]:
        penalty = min(25, (max_underlying - targets["max_underlying_share"]) * 0.8)
        score -= penalty
        issues.append(f"Underlying concentration is high at {max_underlying:.1f}%.")

    if max_expiry > targets["max_expiry_share"]:
        penalty = min(20, (max_expiry - targets["max_expiry_share"]) * 0.6)
        score -= penalty
        issues.append(f"Expiration concentration is high at {max_expiry:.1f}%.")

    if max_strategy > targets["max_strategy_share"]:
        penalty = min(20, (max_strategy - targets["max_strategy_share"]) * 0.6)
        score -= penalty
        issues.append(f"Strategy concentration is high at {max_strategy:.1f}%.")

    if int(strategy_mix.get("strategy_count", 0)) < int(targets["min_strategy_count"]):
        score -= 15
        issues.append("Strategy count is below target diversification level.")

    if isinstance(by_bucket, pd.DataFrame) and not by_bucket.empty:
        buckets = set(by_bucket["strategy_bucket"].astype(str).tolist())
        if "Hedge" not in buckets:
            score -= 8
            issues.append("No hedge bucket detected.")
        if "Volatility" not in buckets:
            score -= 5
            issues.append("No dedicated volatility bucket detected.")

    score = round(max(0, min(100, score)), 2)

    if score >= 80:
        level = "STRONG"
    elif score >= 60:
        level = "ADEQUATE"
    elif score >= 40:
        level = "WEAK"
    else:
        level = "CRITICAL"

    return {
        "available": True,
        "diversification_score": score,
        "diversification_level": level,
        "issues": issues or ["No major diversification issues detected."],
        "max_underlying_allocation": round(max_underlying, 2),
        "max_expiry_allocation": round(max_expiry, 2),
        "max_strategy_allocation": round(max_strategy, 2),
    }


def generate_construction_recommendations(positions: Any, targets: dict[str, float] | None = None) -> dict[str, Any]:
    targets = targets or DEFAULT_TARGETS
    df = normalize_risk_positions(positions)
    if df.empty:
        return _empty("No positions available.")

    allocation = analyze_capital_allocation(df)
    risk_budget = calculate_risk_budget(df)
    diversification = diagnose_diversification(df, targets)

    recs = []

    by_underlying = allocation.get("by_underlying")
    if isinstance(by_underlying, pd.DataFrame) and not by_underlying.empty:
        top = by_underlying.iloc[0]
        if float(top.get("allocation_pct", 0)) > targets["max_underlying_share"]:
            recs.append({
                "Priority": "High",
                "Action": "Reduce Underlying Concentration",
                "Target": top.get("underlying", "Unknown"),
                "Rationale": f"{top.get('underlying')} represents {top.get('allocation_pct')}% of notional allocation.",
            })

    by_expiry = allocation.get("by_expiry")
    if isinstance(by_expiry, pd.DataFrame) and not by_expiry.empty:
        top = by_expiry.iloc[0]
        if float(top.get("allocation_pct", 0)) > targets["max_expiry_share"]:
            recs.append({
                "Priority": "Medium",
                "Action": "Stagger Expiration Exposure",
                "Target": top.get("expiry", "Unknown"),
                "Rationale": f"Expiry {top.get('expiry')} represents {top.get('allocation_pct')}% of notional allocation.",
            })

    rb = risk_budget.get("risk_by_bucket")
    if isinstance(rb, pd.DataFrame) and not rb.empty:
        top = rb.iloc[0]
        if float(top.get("risk_budget_pct", 0)) > 50:
            recs.append({
                "Priority": "High",
                "Action": "Rebalance Risk Budget",
                "Target": top.get("strategy_bucket", "Unknown"),
                "Rationale": f"{top.get('strategy_bucket')} consumes {top.get('risk_budget_pct')}% of total risk budget.",
            })

    for issue in diversification.get("issues", []):
        if "No hedge" in issue:
            recs.append({
                "Priority": "Medium",
                "Action": "Add Hedge Bucket",
                "Target": "Portfolio",
                "Rationale": "No hedge bucket detected. Consider protective puts, collars, or index hedges.",
            })
        elif "No dedicated volatility" in issue:
            recs.append({
                "Priority": "Low",
                "Action": "Add Volatility Bucket",
                "Target": "Portfolio",
                "Rationale": "No volatility bucket detected. Consider calendars, diagonals, or defined-risk vol structures.",
            })

    if not recs:
        recs.append({
            "Priority": "Normal",
            "Action": "Maintain Portfolio Construction",
            "Target": "Portfolio",
            "Rationale": "Allocation, diversification, and risk budget are within configured targets.",
        })

    return {
        "available": True,
        "recommendations": pd.DataFrame(recs),
    }


def score_portfolio_construction(positions: Any, targets: dict[str, float] | None = None) -> dict[str, Any]:
    targets = targets or DEFAULT_TARGETS
    diversification = diagnose_diversification(positions, targets)
    risk_budget = calculate_risk_budget(positions)

    if not diversification.get("available"):
        return _empty(diversification.get("reason", "Construction score unavailable."))

    score = float(diversification.get("diversification_score", 0))
    drivers = list(diversification.get("issues", []))

    rb = risk_budget.get("risk_by_bucket")
    if isinstance(rb, pd.DataFrame) and not rb.empty:
        max_risk_bucket = float(rb["risk_budget_pct"].max())
        if max_risk_bucket > 60:
            score -= 15
            drivers.append(f"Risk budget is dominated by one bucket at {max_risk_bucket:.1f}%.")
        elif max_risk_bucket > 45:
            score -= 8
            drivers.append(f"Risk budget is moderately concentrated at {max_risk_bucket:.1f}%.")

    score = round(max(0, min(100, score)), 2)

    if score >= 80:
        level = "INSTITUTIONAL"
    elif score >= 60:
        level = "BALANCED"
    elif score >= 40:
        level = "NEEDS_REBALANCE"
    else:
        level = "FRAGILE"

    return {
        "available": True,
        "construction_score": score,
        "construction_level": level,
        "drivers": drivers,
    }


def build_portfolio_construction_report(positions: Any, targets: dict[str, float] | None = None) -> dict[str, Any]:
    df = normalize_risk_positions(positions)
    if df.empty:
        return {"available": False, "reason": "No options positions available.", "positions": df}

    targets = targets or DEFAULT_TARGETS

    strategy_mix = analyze_strategy_mix(df)
    allocation = analyze_capital_allocation(df)
    risk_budget = calculate_risk_budget(df)
    diversification = diagnose_diversification(df, targets)
    recommendations = generate_construction_recommendations(df, targets)
    score = score_portfolio_construction(df, targets)

    return {
        "available": True,
        "positions": df,
        "targets": targets,
        "strategy_mix": strategy_mix,
        "allocation": allocation,
        "risk_budget": risk_budget,
        "diversification": diversification,
        "recommendations": recommendations,
        "score": score,
    }


def summarize_portfolio_construction(report: dict[str, Any]) -> str:
    if not report.get("available"):
        return f"Portfolio construction unavailable: {report.get('reason', 'unknown reason')}"

    score = report.get("score", {})
    diversification = report.get("diversification", {})

    return (
        f"Portfolio construction is {score.get('construction_level')} "
        f"({score.get('construction_score')}/100). "
        f"Diversification is {diversification.get('diversification_level')} "
        f"({diversification.get('diversification_score')}/100)."
    )
