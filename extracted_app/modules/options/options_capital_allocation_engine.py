"""
Sprint 6 Phase 4 — Capital Allocation Intelligence Engine.

Institutional capital allocation layer for options trading:
- Capital sleeve allocation
- Risk-budget allocation
- Strategy allocation targets
- Opportunity allocation scoring
- Capital efficiency diagnostics
- Rebalance recommendations

Designed to sit after:
Strategy Factory -> Liquidity -> Position Sizing -> Capital Allocation
"""
from __future__ import annotations

from typing import Any
import pandas as pd


DEFAULT_SLEEVES = {
    "Income": 0.35,
    "Directional": 0.30,
    "Volatility": 0.20,
    "Hedge": 0.10,
    "Opportunistic": 0.05,
}


DEFAULT_RISK_WEIGHTS = {
    "Income": 0.75,
    "Directional": 1.00,
    "Volatility": 1.25,
    "Hedge": 0.50,
    "Opportunistic": 1.50,
}


def _frame(data: Any) -> pd.DataFrame:
    if data is None:
        return pd.DataFrame()
    if isinstance(data, pd.DataFrame):
        return data.copy()
    if isinstance(data, list):
        return pd.DataFrame(data)
    return pd.DataFrame()


def _num(series: pd.Series, default: float = 0.0) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(default)


def normalize_opportunities(opportunities: Any) -> pd.DataFrame:
    df = _frame(opportunities)
    if df.empty:
        return df

    df = df.copy()

    defaults = {
        "ticker": "",
        "underlying": "",
        "strategy": "",
        "strategy_bucket": "",
        "direction": "",
        "conviction": 50,
        "expected_return": 0,
        "max_loss": 0,
        "risk_reward": 0,
        "probability_of_profit": 0,
        "liquidity_score": 50,
        "greeks_risk_score": 50,
        "capital_required": 0,
        "recommended_contracts": 0,
    }

    for col, default in defaults.items():
        if col not in df.columns:
            df[col] = default

    for col in [
        "conviction",
        "expected_return",
        "max_loss",
        "risk_reward",
        "probability_of_profit",
        "liquidity_score",
        "greeks_risk_score",
        "capital_required",
        "recommended_contracts",
    ]:
        df[col] = _num(df[col])

    df["ticker"] = (
        df["ticker"]
        .fillna("")
        .astype(str)
        .replace("", pd.NA)
        .fillna(df["underlying"].fillna("").astype(str))
        .fillna("")
        .astype(str)
        .str.upper()
    )

    df["strategy"] = df["strategy"].fillna("Unclassified").replace("", "Unclassified").astype(str)
    df["strategy_bucket"] = (
        df["strategy_bucket"]
        .fillna("")
        .astype(str)
        .replace("", pd.NA)
        .fillna(df["strategy"].apply(classify_strategy_bucket))
        .fillna("Opportunistic")
        .astype(str)
    )

    return df


def classify_strategy_bucket(strategy: Any) -> str:
    s = str(strategy or "").lower()

    if any(x in s for x in ["covered", "cash secured", "credit", "income", "condor", "short premium"]):
        return "Income"
    if any(x in s for x in ["straddle", "strangle", "calendar", "diagonal", "volatility", "long vol"]):
        return "Volatility"
    if any(x in s for x in ["hedge", "protective", "collar"]):
        return "Hedge"
    if any(x in s for x in ["call", "put", "debit", "spread", "directional"]):
        return "Directional"

    return "Opportunistic"


def build_capital_sleeves(
    portfolio_value: float,
    sleeve_targets: dict[str, float] | None = None,
    cash_buffer_pct: float = 0.10,
) -> dict[str, Any]:
    sleeve_targets = sleeve_targets or DEFAULT_SLEEVES
    investable_capital = max(0.0, float(portfolio_value) * (1.0 - float(cash_buffer_pct)))

    rows = []
    for sleeve, pct in sleeve_targets.items():
        allocation = investable_capital * float(pct)
        rows.append({
            "Sleeve": sleeve,
            "Target %": round(float(pct) * 100, 2),
            "Allocated Capital": round(allocation, 2),
            "Risk Weight": DEFAULT_RISK_WEIGHTS.get(sleeve, 1.0),
            "Risk-Adjusted Capital": round(allocation / max(0.01, DEFAULT_RISK_WEIGHTS.get(sleeve, 1.0)), 2),
        })

    table = pd.DataFrame(rows)

    return {
        "available": True,
        "portfolio_value": round(float(portfolio_value), 2),
        "cash_buffer_pct": round(float(cash_buffer_pct) * 100, 2),
        "cash_buffer": round(float(portfolio_value) * float(cash_buffer_pct), 2),
        "investable_capital": round(investable_capital, 2),
        "sleeves": table,
    }


def score_allocation_opportunities(opportunities: Any) -> dict[str, Any]:
    df = normalize_opportunities(opportunities)
    if df.empty:
        return {"available": False, "reason": "No opportunities available.", "opportunities": df}

    df = df.copy()

    # Normalize expected return if passed as decimal.
    expected = df["expected_return"].copy()
    expected = expected.where(expected.abs() > 1, expected * 100)

    pop = df["probability_of_profit"].copy()
    pop = pop.where(pop > 1, pop * 100)

    risk_penalty = df["greeks_risk_score"].clip(lower=0, upper=100)
    liquidity = df["liquidity_score"].clip(lower=0, upper=100)
    conviction = df["conviction"].clip(lower=0, upper=100)

    rr = df["risk_reward"].clip(lower=0, upper=10)

    df["allocation_score"] = (
        conviction * 0.30
        + liquidity * 0.20
        + pop.clip(0, 100) * 0.20
        + expected.clip(-50, 100) * 0.15
        + rr * 5.0 * 0.10
        - risk_penalty * 0.15
    ).clip(lower=0, upper=100).round(2)

    df["allocation_priority"] = df["allocation_score"].apply(
        lambda x: "HIGH" if x >= 75 else "MEDIUM" if x >= 55 else "LOW" if x >= 35 else "AVOID"
    )

    return {"available": True, "opportunities": df.sort_values("allocation_score", ascending=False).reset_index(drop=True)}


def allocate_capital_to_opportunities(
    portfolio_value: float,
    opportunities: Any,
    sleeve_targets: dict[str, float] | None = None,
    cash_buffer_pct: float = 0.10,
    max_single_trade_pct: float = 0.05,
) -> dict[str, Any]:
    scored = score_allocation_opportunities(opportunities)
    sleeves = build_capital_sleeves(portfolio_value, sleeve_targets, cash_buffer_pct)

    if not scored.get("available"):
        return {
            "available": False,
            "reason": scored.get("reason", "No opportunities available."),
            "allocations": pd.DataFrame(),
            "sleeves": sleeves,
        }

    df = scored["opportunities"].copy()
    sleeve_table = sleeves["sleeves"].copy()

    sleeve_budget = dict(zip(sleeve_table["Sleeve"], sleeve_table["Allocated Capital"]))
    remaining = dict(sleeve_budget)

    max_single_trade = float(portfolio_value) * float(max_single_trade_pct)

    rows = []
    for _, row in df.iterrows():
        bucket = str(row.get("strategy_bucket") or "Opportunistic")
        if bucket not in remaining:
            bucket = "Opportunistic"

        available = float(remaining.get(bucket, 0))
        if available <= 0:
            allocation = 0.0
        else:
            score_factor = float(row.get("allocation_score", 0)) / 100.0
            requested = float(row.get("capital_required") or 0)

            if requested <= 0:
                requested = available * score_factor * 0.25

            allocation = min(available, max_single_trade, requested)

            if row.get("allocation_priority") == "LOW":
                allocation *= 0.50
            elif row.get("allocation_priority") == "AVOID":
                allocation = 0.0

        remaining[bucket] = max(0.0, float(remaining.get(bucket, 0)) - allocation)

        rows.append({
            "Ticker": row.get("ticker", ""),
            "Strategy": row.get("strategy", ""),
            "Sleeve": bucket,
            "Allocation Score": row.get("allocation_score", 0),
            "Priority": row.get("allocation_priority", "LOW"),
            "Requested Capital": round(float(row.get("capital_required") or 0), 2),
            "Allocated Capital": round(allocation, 2),
            "Recommended Contracts": int(row.get("recommended_contracts") or 0),
            "Liquidity Score": row.get("liquidity_score", 0),
            "Greeks Risk Score": row.get("greeks_risk_score", 0),
            "Conviction": row.get("conviction", 0),
        })

    allocations = pd.DataFrame(rows)
    remaining_table = pd.DataFrame([
        {
            "Sleeve": sleeve,
            "Starting Budget": round(float(sleeve_budget.get(sleeve, 0)), 2),
            "Remaining Budget": round(float(remaining.get(sleeve, 0)), 2),
            "Allocated": round(float(sleeve_budget.get(sleeve, 0)) - float(remaining.get(sleeve, 0)), 2),
            "Utilization %": round(
                ((float(sleeve_budget.get(sleeve, 0)) - float(remaining.get(sleeve, 0))) / max(1.0, float(sleeve_budget.get(sleeve, 0)))) * 100,
                2,
            ),
        }
        for sleeve in sleeve_budget.keys()
    ])

    return {
        "available": True,
        "allocations": allocations,
        "sleeves": sleeve_table,
        "remaining": remaining_table,
        "scored_opportunities": df,
        "portfolio_value": round(float(portfolio_value), 2),
        "max_single_trade": round(max_single_trade, 2),
    }


def diagnose_capital_efficiency(allocation_report: dict[str, Any]) -> dict[str, Any]:
    if not allocation_report.get("available"):
        return {"available": False, "reason": allocation_report.get("reason", "No allocation report available.")}

    allocations = allocation_report.get("allocations")
    remaining = allocation_report.get("remaining")

    if not isinstance(allocations, pd.DataFrame) or allocations.empty:
        return {"available": False, "reason": "No allocations available."}

    total_allocated = float(allocations["Allocated Capital"].sum())
    portfolio_value = float(allocation_report.get("portfolio_value", 0) or 0)
    investable = float(allocation_report.get("sleeves", pd.DataFrame()).get("Allocated Capital", pd.Series(dtype=float)).sum() or 0)

    utilization = round(total_allocated / max(1.0, investable) * 100, 2)
    high_priority_funded = int(((allocations["Priority"] == "HIGH") & (allocations["Allocated Capital"] > 0)).sum())
    unfunded_high = int(((allocations["Priority"] == "HIGH") & (allocations["Allocated Capital"] <= 0)).sum())

    score = 100.0
    issues = []

    if utilization < 25:
        score -= 25
        issues.append("Low capital deployment against investable budget.")
    elif utilization > 90:
        score -= 10
        issues.append("Very high capital deployment; cash flexibility may be limited.")

    if unfunded_high > 0:
        score -= min(25, unfunded_high * 8)
        issues.append(f"{unfunded_high} high-priority opportunities were not funded.")

    if isinstance(remaining, pd.DataFrame) and not remaining.empty:
        max_util = float(remaining["Utilization %"].max())
        min_util = float(remaining["Utilization %"].min())
        if max_util - min_util > 60:
            score -= 15
            issues.append("Sleeve utilization is imbalanced.")

    score = round(max(0, min(100, score)), 2)

    if score >= 80:
        level = "EFFICIENT"
    elif score >= 60:
        level = "ADEQUATE"
    elif score >= 40:
        level = "INEFFICIENT"
    else:
        level = "POOR"

    return {
        "available": True,
        "capital_efficiency_score": score,
        "capital_efficiency_level": level,
        "portfolio_utilization_pct": utilization,
        "total_allocated": round(total_allocated, 2),
        "investable_capital": round(investable, 2),
        "high_priority_funded": high_priority_funded,
        "unfunded_high_priority": unfunded_high,
        "issues": issues or ["Capital allocation appears balanced."],
    }


def build_capital_allocation_report(
    portfolio_value: float,
    opportunities: Any,
    sleeve_targets: dict[str, float] | None = None,
    cash_buffer_pct: float = 0.10,
    max_single_trade_pct: float = 0.05,
) -> dict[str, Any]:
    allocation = allocate_capital_to_opportunities(
        portfolio_value=portfolio_value,
        opportunities=opportunities,
        sleeve_targets=sleeve_targets,
        cash_buffer_pct=cash_buffer_pct,
        max_single_trade_pct=max_single_trade_pct,
    )

    efficiency = diagnose_capital_efficiency(allocation)

    return {
        **allocation,
        "efficiency": efficiency,
    }


def summarize_capital_allocation(report: dict[str, Any]) -> str:
    if not report.get("available"):
        return f"Capital allocation unavailable: {report.get('reason', 'unknown reason')}"

    efficiency = report.get("efficiency", {})
    total_allocated = efficiency.get("total_allocated", 0)
    utilization = efficiency.get("portfolio_utilization_pct", 0)

    return (
        f"Capital efficiency is {efficiency.get('capital_efficiency_level')} "
        f"({efficiency.get('capital_efficiency_score')}/100). "
        f"Allocated ${total_allocated:,.2f}, using {utilization}% of investable capital."
    )
