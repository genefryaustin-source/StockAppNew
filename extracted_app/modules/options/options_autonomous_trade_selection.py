"""
Sprint 12 Phase 2 — Autonomous Trade Selection Engine.

Autonomous Institutional Options CIO layer:
- Candidate trade normalization
- Multi-signal trade scoring
- Portfolio optimization / liquidity / vol / market-maker overlays
- Capital-aware trade ranking
- Trade approval / watch / reject classification
- Autonomous trade-selection playbook

This module does not place trades. It creates deterministic trade-selection guidance.
"""
from __future__ import annotations

from typing import Any
import pandas as pd


DEFAULT_TRADE_SELECTION_POLICY = {
    "min_trade_score": 65.0,
    "approval_score": 80.0,
    "max_capital_per_trade_pct": 10.0,
    "min_liquidity_score": 50.0,
    "max_assignment_probability": 45.0,
    "min_annualized_yield": 8.0,
    "risk_weight": 0.25,
    "income_weight": 0.20,
    "liquidity_weight": 0.20,
    "market_structure_weight": 0.20,
    "portfolio_fit_weight": 0.15,
}


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _safe_get(d: Any, path: list[str], default: Any = None) -> Any:
    cur = d
    for key in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
    return default if cur is None else cur


def _df(value: Any) -> pd.DataFrame:
    if isinstance(value, pd.DataFrame):
        return value.copy()
    if isinstance(value, list):
        return pd.DataFrame(value)
    return pd.DataFrame()


def _priority_score(priority: Any) -> int:
    p = str(priority).upper()
    if p == "APPROVED":
        return 0
    if p == "HIGH":
        return 1
    if p == "WATCH":
        return 2
    if p == "NORMAL":
        return 3
    if p == "REJECT":
        return 9
    return 5


def normalize_trade_candidates(candidates: Any) -> pd.DataFrame:
    df = _df(candidates)
    if df.empty:
        return df

    df = df.copy()

    defaults = {
        "underlying": "",
        "symbol": "",
        "option_symbol": "",
        "strategy": "",
        "trade_type": "",
        "side": "",
        "expiry": "",
        "dte": 0,
        "strike": 0,
        "premium": 0,
        "mid": 0,
        "required_capital": 0,
        "max_loss": 0,
        "max_profit": 0,
        "annualized_yield": 0,
        "return_on_capital": 0,
        "probability_profit": 50,
        "assignment_probability": 0,
        "liquidity_score": 50,
        "opportunity_score": 50,
        "delta": 0,
        "gamma": 0,
        "theta": 0,
        "vega": 0,
        "iv": 0,
    }

    for col, default in defaults.items():
        if col not in df.columns:
            df[col] = default

    for col in [
        "dte", "strike", "premium", "mid", "required_capital", "max_loss",
        "max_profit", "annualized_yield", "return_on_capital", "probability_profit",
        "assignment_probability", "liquidity_score", "opportunity_score",
        "delta", "gamma", "theta", "vega", "iv",
    ]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["underlying"] = (
        df["underlying"]
        .fillna("")
        .astype(str)
        .replace("", pd.NA)
        .fillna(df["symbol"].fillna("").astype(str))
        .fillna("")
        .astype(str)
        .str.upper()
    )

    return df


def build_candidates_from_reports(
    csp_report: dict[str, Any] | None = None,
    covered_call_report: dict[str, Any] | None = None,
    wheel_report: dict[str, Any] | None = None,
    income_command_report: dict[str, Any] | None = None,
    volatility_command_report: dict[str, Any] | None = None,
    market_maker_report: dict[str, Any] | None = None,
) -> pd.DataFrame:
    rows = []

    csp = _df((csp_report or {}).get("approved"))
    if not csp.empty:
        for _, row in csp.iterrows():
            rows.append({
                "Source": "Cash Secured Put Factory",
                "underlying": row.get("underlying", ""),
                "option_symbol": row.get("option_symbol", ""),
                "strategy": "Cash Secured Put",
                "trade_type": "Income",
                "side": "SELL_PUT",
                "expiry": row.get("expiry", ""),
                "dte": row.get("dte", 0),
                "strike": row.get("strike", 0),
                "premium": row.get("mid", 0),
                "required_capital": row.get("Required Capital", 0),
                "annualized_yield": row.get("Annualized Yield %", 0),
                "return_on_capital": row.get("Return On Capital %", 0),
                "assignment_probability": row.get("Assignment Probability %", 0),
                "liquidity_score": row.get("liquidity_score", 50),
                "opportunity_score": row.get("Opportunity Score", 50),
                "delta": row.get("delta", 0),
                "gamma": row.get("gamma", 0),
                "theta": row.get("theta", 0),
                "vega": row.get("vega", 0),
                "iv": row.get("iv", 0),
            })

    cc = _df((covered_call_report or {}).get("candidates"))
    if not cc.empty:
        for _, row in cc.iterrows():
            rows.append({
                "Source": "Covered Call Factory",
                "underlying": row.get("Underlying", row.get("underlying", "")),
                "option_symbol": row.get("option_symbol", ""),
                "strategy": "Covered Call",
                "trade_type": "Income",
                "side": "SELL_CALL",
                "expiry": row.get("expiry", ""),
                "dte": row.get("dte", 0),
                "strike": row.get("strike", 0),
                "premium": row.get("premium", row.get("mid", 0)),
                "required_capital": 0,
                "annualized_yield": row.get("Estimated Annual Yield %", row.get("annualized_yield", 0)),
                "return_on_capital": row.get("return_on_capital", 0),
                "assignment_probability": 0,
                "liquidity_score": row.get("liquidity_score", 60),
                "opportunity_score": row.get("Opportunity Score", 60),
                "delta": row.get("delta", 0),
                "gamma": row.get("gamma", 0),
                "theta": row.get("theta", 0),
                "vega": row.get("vega", 0),
                "iv": row.get("iv", 0),
            })

    wheel = _df((wheel_report or {}).get("action_queue"))
    if not wheel.empty:
        for _, row in wheel.iterrows():
            rows.append({
                "Source": "Wheel Command Center",
                "underlying": row.get("underlying", ""),
                "option_symbol": row.get("option_symbol", ""),
                "strategy": row.get("Wheel Stage", "Wheel"),
                "trade_type": "Wheel",
                "side": row.get("Recommended Wheel Action", "Review"),
                "expiry": row.get("expiry", ""),
                "dte": row.get("dte", 0),
                "strike": row.get("strike", 0),
                "premium": row.get("premium", row.get("mid", 0)),
                "required_capital": 0,
                "annualized_yield": row.get("Annualized Wheel Yield", 0),
                "return_on_capital": 0,
                "assignment_probability": 0,
                "liquidity_score": row.get("liquidity_score", 50),
                "opportunity_score": row.get("Wheel Score", 50),
                "delta": row.get("delta", 0),
                "gamma": row.get("gamma", 0),
                "theta": row.get("theta", 0),
                "vega": row.get("vega", 0),
                "iv": row.get("iv", 0),
            })

    volq = _df(_safe_get(volatility_command_report, ["opportunities", "opportunities"], pd.DataFrame()))
    if not volq.empty:
        for _, row in volq.iterrows():
            rows.append({
                "Source": "Volatility Command",
                "underlying": "",
                "option_symbol": "",
                "strategy": row.get("Opportunity", "Volatility Structure"),
                "trade_type": "Volatility",
                "side": row.get("Candidate Structures", ""),
                "expiry": "",
                "dte": 0,
                "strike": 0,
                "premium": 0,
                "required_capital": 0,
                "annualized_yield": 0,
                "return_on_capital": 0,
                "assignment_probability": 0,
                "liquidity_score": 60,
                "opportunity_score": 75 if str(row.get("Priority", "")).upper() == "HIGH" else 60,
            })

    mmq = _df(_safe_get(market_maker_report, ["opportunities", "opportunity_queue"], pd.DataFrame()))
    if not mmq.empty:
        for _, row in mmq.iterrows():
            rows.append({
                "Source": "Market Maker Command",
                "underlying": "",
                "option_symbol": "",
                "strategy": row.get("Recommendation", "Market Maker Structure"),
                "trade_type": "Market Structure",
                "side": row.get("Structures", ""),
                "expiry": "",
                "dte": 0,
                "strike": 0,
                "premium": 0,
                "required_capital": 0,
                "annualized_yield": 0,
                "return_on_capital": 0,
                "assignment_probability": 0,
                "liquidity_score": 60,
                "opportunity_score": 75 if str(row.get("Priority", "")).upper() == "HIGH" else 60,
            })

    return normalize_trade_candidates(pd.DataFrame(rows))


def score_trade_candidate(
    row: pd.Series,
    portfolio_optimization_report: dict[str, Any] | None = None,
    volatility_command_report: dict[str, Any] | None = None,
    market_maker_report: dict[str, Any] | None = None,
    policy: dict[str, Any] | None = None,
    portfolio_value: float = 100000.0,
) -> dict[str, Any]:
    policy = policy or DEFAULT_TRADE_SELECTION_POLICY

    liquidity = _num(row.get("liquidity_score"), 50)
    annual_yield = _num(row.get("annualized_yield"), 0)
    roc = _num(row.get("return_on_capital"), 0)
    assignment = _num(row.get("assignment_probability"), 0)
    opportunity = _num(row.get("opportunity_score"), 50)
    capital = _num(row.get("required_capital"), 0)
    gamma = abs(_num(row.get("gamma"), 0))
    dte = _num(row.get("dte"), 0)

    objective_score = _num(_safe_get(portfolio_optimization_report, ["summary", "objective_score"], 65), 65)
    vol_rating = str(_safe_get(volatility_command_report, ["score", "rating"], "NORMAL"))
    mm_rating = str(_safe_get(market_maker_report, ["score", "rating"], "NORMAL"))

    risk_component = 100.0
    flags = []

    if assignment > policy["max_assignment_probability"]:
        risk_component -= 25
        flags.append("Assignment probability exceeds policy.")

    if gamma > 0.10 and dte <= 14:
        risk_component -= 20
        flags.append("Near-term gamma risk is elevated.")

    if capital > 0 and portfolio_value > 0:
        capital_pct = capital / portfolio_value * 100
        if capital_pct > policy["max_capital_per_trade_pct"]:
            risk_component -= 25
            flags.append("Capital requirement exceeds per-trade policy.")
    else:
        capital_pct = 0

    if vol_rating in {"HIGH", "EXTREME"}:
        risk_component -= 10
        flags.append("Volatility command rating is elevated.")

    if mm_rating in {"HIGH", "EXTREME"}:
        risk_component -= 10
        flags.append("Market-maker command rating is elevated.")

    income_component = min(100, max(annual_yield, roc * 4))
    liquidity_component = liquidity
    market_structure_component = 70.0

    if vol_rating in {"LOW", "NORMAL"}:
        market_structure_component += 5
    elif vol_rating in {"HIGH", "EXTREME"}:
        market_structure_component -= 10

    if mm_rating in {"LOW", "NORMAL"}:
        market_structure_component += 5
    elif mm_rating in {"HIGH", "EXTREME"}:
        market_structure_component -= 10

    portfolio_fit_component = objective_score
    if opportunity:
        portfolio_fit_component = (portfolio_fit_component + opportunity) / 2

    trade_score = (
        max(0, risk_component) * policy["risk_weight"]
        + income_component * policy["income_weight"]
        + liquidity_component * policy["liquidity_weight"]
        + max(0, min(100, market_structure_component)) * policy["market_structure_weight"]
        + portfolio_fit_component * policy["portfolio_fit_weight"]
    )

    trade_score = round(max(0, min(100, trade_score)), 2)

    if trade_score >= policy["approval_score"]:
        decision = "APPROVED"
        priority = "High"
    elif trade_score >= policy["min_trade_score"]:
        decision = "WATCHLIST"
        priority = "Medium"
    else:
        decision = "REJECT"
        priority = "Low"

    if liquidity < policy["min_liquidity_score"]:
        decision = "REJECT" if trade_score < 75 else "WATCHLIST"
        flags.append("Liquidity is below policy.")

    return {
        "Trade Score": trade_score,
        "Decision": decision,
        "Priority": priority,
        "Risk Component": round(max(0, risk_component), 2),
        "Income Component": round(income_component, 2),
        "Liquidity Component": round(liquidity_component, 2),
        "Market Structure Component": round(max(0, min(100, market_structure_component)), 2),
        "Portfolio Fit Component": round(portfolio_fit_component, 2),
        "Capital %": round(capital_pct, 2),
        "Trade Flags": "; ".join(flags) if flags else "No major trade-selection flags.",
    }


def build_autonomous_trade_selection_report(
    candidates: Any = None,
    portfolio_value: float = 100000.0,
    portfolio_optimization_report: dict[str, Any] | None = None,
    csp_report: dict[str, Any] | None = None,
    covered_call_report: dict[str, Any] | None = None,
    wheel_report: dict[str, Any] | None = None,
    income_command_report: dict[str, Any] | None = None,
    volatility_command_report: dict[str, Any] | None = None,
    market_maker_report: dict[str, Any] | None = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or DEFAULT_TRADE_SELECTION_POLICY

    if candidates is None:
        df = build_candidates_from_reports(
            csp_report=csp_report,
            covered_call_report=covered_call_report,
            wheel_report=wheel_report,
            income_command_report=income_command_report,
            volatility_command_report=volatility_command_report,
            market_maker_report=market_maker_report,
        )
    else:
        df = normalize_trade_candidates(candidates)

    if df.empty:
        return {
            "available": False,
            "reason": "No trade candidates available.",
            "candidates": df,
        }

    scored = pd.DataFrame([
        score_trade_candidate(
            row=row,
            portfolio_optimization_report=portfolio_optimization_report,
            volatility_command_report=volatility_command_report,
            market_maker_report=market_maker_report,
            policy=policy,
            portfolio_value=portfolio_value,
        )
        for _, row in df.iterrows()
    ])

    enriched = pd.concat([df.reset_index(drop=True), scored.reset_index(drop=True)], axis=1)

    ranked = enriched.sort_values(["Trade Score", "opportunity_score", "liquidity_score"], ascending=False).reset_index(drop=True)
    approved = ranked[ranked["Decision"].eq("APPROVED")].copy()
    watchlist = ranked[ranked["Decision"].eq("WATCHLIST")].copy()
    rejected = ranked[ranked["Decision"].eq("REJECT")].copy()

    summary = {
        "candidate_count": int(len(ranked)),
        "approved_count": int(len(approved)),
        "watchlist_count": int(len(watchlist)),
        "rejected_count": int(len(rejected)),
        "top_trade_score": round(float(ranked["Trade Score"].max()), 2),
        "avg_trade_score": round(float(ranked["Trade Score"].mean()), 2),
        "top_decision": str(ranked["Decision"].iloc[0]) if not ranked.empty else "NONE",
        "top_strategy": str(ranked["strategy"].iloc[0]) if not ranked.empty else "NONE",
    }

    return {
        "available": True,
        "summary": summary,
        "ranked_candidates": ranked,
        "approved": approved,
        "watchlist": watchlist,
        "rejected": rejected,
        "policy": policy,
    }


def generate_trade_selection_playbook(report: dict[str, Any]) -> dict[str, Any]:
    if not report.get("available"):
        return {
            "available": False,
            "reason": report.get("reason", "No report available."),
            "playbook": pd.DataFrame(),
        }

    s = report.get("summary", {})
    rows = []

    if s.get("approved_count", 0) > 0:
        rows.append({
            "Step": 1,
            "Playbook": "Approve Top Trades",
            "Priority": "High",
            "Action": f"Review and approve {s.get('approved_count')} top-ranked trade candidates.",
        })

    if s.get("watchlist_count", 0) > 0:
        rows.append({
            "Step": 2,
            "Playbook": "Monitor Watchlist",
            "Priority": "Medium",
            "Action": f"Track {s.get('watchlist_count')} watchlist candidates for better pricing or lower risk.",
        })

    if s.get("approved_count", 0) == 0:
        rows.append({
            "Step": 1,
            "Playbook": "No Autonomous Approval",
            "Priority": "Normal",
            "Action": "No trade meets autonomous approval criteria. Wait or adjust candidate universe.",
        })

    return {
        "available": True,
        "playbook": pd.DataFrame(rows),
    }


def summarize_autonomous_trade_selection(report: dict[str, Any]) -> str:
    if not report.get("available"):
        return f"Autonomous Trade Selection unavailable: {report.get('reason', 'unknown reason')}"

    s = report.get("summary", {})
    return (
        f"Autonomous Trade Selection reviewed {s.get('candidate_count')} candidates. "
        f"{s.get('approved_count')} were approved, {s.get('watchlist_count')} were placed on watchlist, "
        f"and {s.get('rejected_count')} were rejected. "
        f"Top trade score is {s.get('top_trade_score')}/100 with decision {s.get('top_decision')}."
    )
