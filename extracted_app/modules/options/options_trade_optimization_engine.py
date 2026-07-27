"""
Sprint 6 Phase 5 — Trade Optimization Engine.

Institutional trade optimization layer:
- Scores candidate trades
- Combines conviction, liquidity, risk, capital efficiency, and execution quality
- Produces optimal trade ranking
- Flags trades to avoid
- Generates trade sizing and routing guidance
- Provides deterministic fallback behavior

Designed to sit after:
Strategy Factory -> Liquidity -> Position Sizing -> Capital Allocation -> Trade Optimization
"""
from __future__ import annotations

from typing import Any
import pandas as pd


DEFAULT_OPTIMIZATION_WEIGHTS = {
    "conviction": 0.25,
    "liquidity": 0.20,
    "risk_reward": 0.18,
    "capital_efficiency": 0.15,
    "execution_quality": 0.12,
    "risk_penalty": 0.10,
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


def normalize_trade_candidates(candidates: Any) -> pd.DataFrame:
    df = _frame(candidates)
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
        "probability_of_profit": 0,
        "risk_reward": 0,
        "max_loss": 0,
        "capital_required": 0,
        "allocated_capital": 0,
        "recommended_contracts": 0,
        "liquidity_score": 50,
        "execution_score": 70,
        "greeks_risk_score": 50,
        "portfolio_risk_score": 50,
        "spread_pct": 0,
        "slippage_bps": 0,
        "priority": "",
    }

    for col, default in defaults.items():
        if col not in df.columns:
            df[col] = default

    for col in [
        "conviction",
        "expected_return",
        "probability_of_profit",
        "risk_reward",
        "max_loss",
        "capital_required",
        "allocated_capital",
        "recommended_contracts",
        "liquidity_score",
        "execution_score",
        "greeks_risk_score",
        "portfolio_risk_score",
        "spread_pct",
        "slippage_bps",
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


def calculate_capital_efficiency_score(row: pd.Series) -> float:
    capital = float(row.get("capital_required") or 0)
    allocated = float(row.get("allocated_capital") or 0)
    max_loss = float(row.get("max_loss") or 0)
    expected_return = float(row.get("expected_return") or 0)
    risk_reward = float(row.get("risk_reward") or 0)

    base = 50.0

    if capital > 0 and allocated > 0:
        utilization = min(1.0, allocated / capital)
        base += utilization * 20

    if max_loss > 0 and capital > 0:
        loss_ratio = max_loss / capital
        if loss_ratio <= 0.25:
            base += 15
        elif loss_ratio <= 0.50:
            base += 5
        else:
            base -= 10

    expected = expected_return if abs(expected_return) > 1 else expected_return * 100
    if expected >= 20:
        base += 15
    elif expected >= 10:
        base += 8
    elif expected < 0:
        base -= 15

    if risk_reward >= 3:
        base += 10
    elif risk_reward >= 2:
        base += 5
    elif risk_reward < 1:
        base -= 10

    return round(max(0, min(100, base)), 2)


def calculate_execution_feasibility(row: pd.Series) -> dict[str, Any]:
    liquidity = float(row.get("liquidity_score") or 0)
    execution = float(row.get("execution_score") or 0)
    spread_pct = float(row.get("spread_pct") or 0)
    slippage_bps = float(row.get("slippage_bps") or 0)

    score = liquidity * 0.55 + execution * 0.35

    # spread_pct can come in decimal or already percent.
    spread_percent = spread_pct * 100 if 0 < spread_pct <= 1 else spread_pct

    if spread_percent > 20:
        score -= 20
    elif spread_percent > 10:
        score -= 10

    if slippage_bps > 250:
        score -= 20
    elif slippage_bps > 100:
        score -= 10

    score = round(max(0, min(100, score)), 2)

    if score >= 80:
        level = "EASY"
        route = "Limit near midpoint"
    elif score >= 65:
        level = "NORMAL"
        route = "Work limit order with patience"
    elif score >= 45:
        level = "DIFFICULT"
        route = "Use smaller clips and avoid market orders"
    else:
        level = "AVOID"
        route = "Avoid unless hedge-critical"

    return {
        "execution_feasibility_score": score,
        "execution_difficulty": level,
        "routing_guidance": route,
    }


def optimize_trade_candidate(row: pd.Series, weights: dict[str, float] | None = None) -> dict[str, Any]:
    weights = weights or DEFAULT_OPTIMIZATION_WEIGHTS

    conviction = float(row.get("conviction") or 0)
    liquidity = float(row.get("liquidity_score") or 0)
    risk_reward = min(100.0, float(row.get("risk_reward") or 0) * 25.0)
    execution = float(row.get("execution_score") or 0)

    cap_eff = calculate_capital_efficiency_score(row)

    greeks_risk = float(row.get("greeks_risk_score") or 0)
    portfolio_risk = float(row.get("portfolio_risk_score") or 0)
    risk_penalty = (greeks_risk * 0.55 + portfolio_risk * 0.45)

    feasibility = calculate_execution_feasibility(row)

    score = (
        conviction * weights.get("conviction", 0.25)
        + liquidity * weights.get("liquidity", 0.20)
        + risk_reward * weights.get("risk_reward", 0.18)
        + cap_eff * weights.get("capital_efficiency", 0.15)
        + execution * weights.get("execution_quality", 0.12)
        - risk_penalty * weights.get("risk_penalty", 0.10)
    )

    # Penalize impossible execution.
    if feasibility["execution_difficulty"] == "AVOID":
        score -= 20
    elif feasibility["execution_difficulty"] == "DIFFICULT":
        score -= 8

    score = round(max(0, min(100, score)), 2)

    if score >= 80:
        action = "APPROVE"
        priority = "HIGH"
    elif score >= 65:
        action = "APPROVE_SMALL"
        priority = "MEDIUM"
    elif score >= 50:
        action = "WATCHLIST"
        priority = "LOW"
    else:
        action = "REJECT"
        priority = "AVOID"

    notes = []
    if conviction >= 75:
        notes.append("High conviction")
    if liquidity < 55:
        notes.append("Liquidity risk")
    if risk_penalty >= 70:
        notes.append("High portfolio/Greeks risk")
    if cap_eff >= 75:
        notes.append("Capital efficient")
    if feasibility["execution_difficulty"] in {"DIFFICULT", "AVOID"}:
        notes.append(f"Execution {feasibility['execution_difficulty'].lower()}")

    return {
        "optimization_score": score,
        "recommended_action": action,
        "optimization_priority": priority,
        "capital_efficiency_score": cap_eff,
        **feasibility,
        "optimization_notes": "; ".join(notes) if notes else "Balanced candidate",
    }


def optimize_trade_candidates(candidates: Any, weights: dict[str, float] | None = None) -> dict[str, Any]:
    df = normalize_trade_candidates(candidates)
    if df.empty:
        return {"available": False, "reason": "No trade candidates available.", "candidates": df}

    rows = [optimize_trade_candidate(row, weights=weights) for _, row in df.iterrows()]
    scores = pd.DataFrame(rows)
    enriched = pd.concat([df.reset_index(drop=True), scores.reset_index(drop=True)], axis=1)

    enriched = enriched.sort_values(
        ["optimization_score", "conviction", "liquidity_score"],
        ascending=False,
    ).reset_index(drop=True)

    approved = int(enriched["recommended_action"].isin(["APPROVE", "APPROVE_SMALL"]).sum())
    rejected = int((enriched["recommended_action"] == "REJECT").sum())
    avg_score = round(float(enriched["optimization_score"].mean()), 2)

    best = enriched.head(1).to_dict("records")[0] if not enriched.empty else {}

    return {
        "available": True,
        "candidates": enriched,
        "summary": {
            "candidate_count": int(len(enriched)),
            "approved_count": approved,
            "rejected_count": rejected,
            "watchlist_count": int((enriched["recommended_action"] == "WATCHLIST").sum()),
            "avg_optimization_score": avg_score,
            "top_candidate": best.get("ticker", "—"),
            "top_strategy": best.get("strategy", "—"),
            "top_score": best.get("optimization_score", 0),
        },
    }


def build_optimization_by_bucket(candidates: Any) -> dict[str, Any]:
    report = optimize_trade_candidates(candidates)
    if not report.get("available"):
        return report

    df = report["candidates"]

    table = (
        df.groupby("strategy_bucket", as_index=False)
        .agg(
            candidates=("strategy_bucket", "size"),
            avg_score=("optimization_score", "mean"),
            approved=("recommended_action", lambda s: int(s.isin(["APPROVE", "APPROVE_SMALL"]).sum())),
            rejected=("recommended_action", lambda s: int((s == "REJECT").sum())),
            avg_liquidity=("liquidity_score", "mean"),
            avg_conviction=("conviction", "mean"),
            avg_risk=("portfolio_risk_score", "mean"),
        )
        .sort_values("avg_score", ascending=False)
        .reset_index(drop=True)
    )

    for col in ["avg_score", "avg_liquidity", "avg_conviction", "avg_risk"]:
        table[col] = pd.to_numeric(table[col], errors="coerce").fillna(0).round(2)

    return {"available": True, "by_bucket": table}


def build_trade_optimization_report(candidates: Any, weights: dict[str, float] | None = None) -> dict[str, Any]:
    optimized = optimize_trade_candidates(candidates, weights=weights)
    if not optimized.get("available"):
        return optimized

    by_bucket = build_optimization_by_bucket(optimized["candidates"])

    top = optimized["candidates"].head(10).copy()
    avoid = optimized["candidates"][optimized["candidates"]["recommended_action"] == "REJECT"].head(10).copy()

    return {
        **optimized,
        "by_bucket": by_bucket,
        "top_trades": top,
        "avoid_trades": avoid,
    }


def summarize_trade_optimization(report: dict[str, Any]) -> str:
    if not report.get("available"):
        return f"Trade optimization unavailable: {report.get('reason', 'unknown reason')}"

    summary = report.get("summary", {})

    return (
        f"Trade optimization reviewed {summary.get('candidate_count')} candidates. "
        f"{summary.get('approved_count')} are approved, {summary.get('watchlist_count')} are watchlist, "
        f"and {summary.get('rejected_count')} are rejected. "
        f"Top candidate is {summary.get('top_candidate')} {summary.get('top_strategy')} "
        f"with score {summary.get('top_score')}/100."
    )
