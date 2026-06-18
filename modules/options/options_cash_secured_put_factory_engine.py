"""
Sprint 9 Phase 4 — Cash Secured Put Factory Engine.
"""
from __future__ import annotations

from typing import Any
import pandas as pd


DEFAULT_CSP_POLICY = {
    "target_delta_min": 0.15,
    "target_delta_max": 0.35,
    "min_annualized_yield": 8.0,
    "max_assignment_probability": 45.0,
    "min_dte": 14,
    "max_dte": 60,
    "min_liquidity_score": 50,
    "cash_buffer_pct": 10.0,
    "contract_multiplier": 100,
}


def _df(data: Any) -> pd.DataFrame:
    if isinstance(data, pd.DataFrame):
        return data.copy()
    if isinstance(data, list):
        return pd.DataFrame(data)
    if isinstance(data, dict):
        if isinstance(data.get("puts"), pd.DataFrame):
            return data["puts"].copy()
        if isinstance(data.get("all_rows"), pd.DataFrame):
            rows = data["all_rows"].copy()
            if "type" in rows.columns:
                return rows[rows["type"].astype(str).str.lower().eq("put")].copy()
            return rows
    return pd.DataFrame()


def _extract_put_chain(chain_data: Any) -> pd.DataFrame:
    if isinstance(chain_data, dict) and isinstance(chain_data.get("chain"), dict):
        rows = []
        for expiry, payload in chain_data["chain"].items():
            if isinstance(payload, dict) and isinstance(payload.get("puts"), pd.DataFrame):
                temp = payload["puts"].copy()
                temp["expiry"] = temp.get("expiry", expiry)
                temp["type"] = temp.get("type", "put")
                rows.append(temp)
        if rows:
            return pd.concat(rows, ignore_index=True)

    df = _df(chain_data)
    if not df.empty and "type" in df.columns:
        df = df[df["type"].astype(str).str.lower().eq("put")].copy()
    return df


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def normalize_put_candidates(chain_data: Any) -> pd.DataFrame:
    df = _extract_put_chain(chain_data)
    if df.empty:
        return df

    df = df.copy()

    defaults = {
        "underlying": "",
        "symbol": "",
        "option_symbol": "",
        "expiry": "",
        "type": "put",
        "strike": 0,
        "bid": 0,
        "ask": 0,
        "last": 0,
        "mid": 0,
        "volume": 0,
        "open_interest": 0,
        "iv": 0,
        "delta": 0,
        "dte": 30,
        "liquidity_score": 50,
    }

    for col, default in defaults.items():
        if col not in df.columns:
            df[col] = default

    for col in ["strike", "bid", "ask", "last", "mid", "volume", "open_interest", "iv", "delta", "dte", "liquidity_score"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["mid"] = df["mid"].where(df["mid"] > 0, ((df["bid"] + df["ask"]) / 2))
    df["mid"] = df["mid"].where(df["mid"] > 0, df["last"])
    df["spread"] = (df["ask"] - df["bid"]).where((df["ask"] > 0) & (df["bid"] > 0), 0)
    df["spread_pct"] = (df["spread"] / df["mid"].replace(0, 1)).clip(lower=0)

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


def calculate_required_capital(row: pd.Series, policy: dict[str, Any] | None = None) -> float:
    policy = policy or DEFAULT_CSP_POLICY
    return round(max(0.0, _num(row.get("strike")) * _num(policy.get("contract_multiplier", 100), 100)), 2)


def calculate_assignment_probability(row: pd.Series) -> float:
    delta = abs(_num(row.get("delta"), 0))
    dte = max(1, _num(row.get("dte"), 30))
    probability = delta * 100
    if dte <= 7:
        probability += 5
    elif dte >= 60:
        probability -= 3
    return round(max(0.0, min(100.0, probability)), 2)


def calculate_put_income_yield(row: pd.Series, policy: dict[str, Any] | None = None) -> dict[str, float]:
    policy = policy or DEFAULT_CSP_POLICY
    premium = _num(row.get("mid"), 0)
    dte = max(1, _num(row.get("dte"), 30))
    capital = calculate_required_capital(row, policy)
    premium_income = premium * _num(policy.get("contract_multiplier", 100), 100)
    roc = premium_income / max(1.0, capital) * 100
    annualized = roc * (365 / dte)
    return {
        "Premium Income": round(premium_income, 2),
        "Required Capital": round(capital, 2),
        "Return On Capital %": round(roc, 2),
        "Annualized Yield %": round(annualized, 2),
    }


def score_put_candidate(row: pd.Series, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = policy or DEFAULT_CSP_POLICY
    delta = abs(_num(row.get("delta"), 0))
    dte = _num(row.get("dte"), 30)
    liquidity = _num(row.get("liquidity_score"), 50)
    volume = _num(row.get("volume"), 0)
    oi = _num(row.get("open_interest"), 0)
    iv = _num(row.get("iv"), 0)
    spread_pct = _num(row.get("spread_pct"), 0)

    assignment_probability = calculate_assignment_probability(row)
    yield_data = calculate_put_income_yield(row, policy)
    annualized_yield = yield_data["Annualized Yield %"]

    score = 50.0
    flags = []

    if policy["target_delta_min"] <= delta <= policy["target_delta_max"]:
        score += 18
        flags.append("Delta is in target range.")
    elif delta > policy["target_delta_max"]:
        score -= 12
        flags.append("Delta is above target.")
    else:
        score -= 5
        flags.append("Delta is below target.")

    if policy["min_dte"] <= dte <= policy["max_dte"]:
        score += 12
        flags.append("DTE is in target range.")
    else:
        score -= 8
        flags.append("DTE is outside target range.")

    if annualized_yield >= policy["min_annualized_yield"]:
        score += 18
        flags.append("Yield meets target.")
    else:
        score -= 10
        flags.append("Yield below target.")

    if assignment_probability <= policy["max_assignment_probability"]:
        score += 10
    else:
        score -= 15
        flags.append("Assignment probability above policy.")

    if liquidity >= policy["min_liquidity_score"] or volume >= 100 or oi >= 500:
        score += 10
    else:
        score -= 15
        flags.append("Liquidity weak.")

    if spread_pct <= 0.10:
        score += 7
    elif spread_pct >= 0.25:
        score -= 10
        flags.append("Wide spread.")

    if iv >= 0.35:
        score += 8

    score = round(max(0, min(100, score)), 2)

    if score >= 80:
        recommendation = "SELL_PUT"
        quality = "STRONG"
    elif score >= 65:
        recommendation = "SELL_SMALL"
        quality = "GOOD"
    elif score >= 50:
        recommendation = "WATCHLIST"
        quality = "WATCH"
    else:
        recommendation = "AVOID"
        quality = "WEAK"

    return {
        **yield_data,
        "Assignment Probability %": assignment_probability,
        "Opportunity Score": score,
        "Opportunity Quality": quality,
        "Recommendation": recommendation,
        "Factory Flags": "; ".join(flags) if flags else "No major flags.",
    }


def rank_put_opportunities(chain_data: Any, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = policy or DEFAULT_CSP_POLICY
    df = normalize_put_candidates(chain_data)

    if df.empty:
        return {"available": False, "reason": "No put option candidates available.", "candidates": df}

    scored = pd.DataFrame([score_put_candidate(row, policy) for _, row in df.iterrows()])
    enriched = pd.concat([df.reset_index(drop=True), scored.reset_index(drop=True)], axis=1)

    ranked = enriched.sort_values(
        ["Opportunity Score", "Annualized Yield %", "open_interest", "volume"],
        ascending=False,
    ).reset_index(drop=True)

    return {"available": True, "candidates": ranked}


def build_cash_secured_put_report(
    chain_data: Any,
    portfolio_cash: float = 100000.0,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or DEFAULT_CSP_POLICY
    ranked = rank_put_opportunities(chain_data, policy)

    if not ranked.get("available"):
        return ranked

    candidates = ranked["candidates"].copy()
    available_cash = max(0.0, float(portfolio_cash) * (1 - float(policy.get("cash_buffer_pct", 10.0)) / 100.0))
    approved = candidates[candidates["Recommendation"].isin(["SELL_PUT", "SELL_SMALL"])].copy()

    if not approved.empty:
        approved["Contracts Fundable"] = approved["Required Capital"].apply(
            lambda capital: int(available_cash // max(1.0, float(capital)))
        )

    summary = {
        "candidate_count": int(len(candidates)),
        "approved_count": int(len(approved)),
        "available_cash": round(available_cash, 2),
        "top10_required_capital": round(float(approved.head(10)["Required Capital"].sum()) if not approved.empty else 0.0, 2),
        "avg_annualized_yield": round(float(candidates["Annualized Yield %"].mean()), 2) if not candidates.empty else 0,
        "avg_assignment_probability": round(float(candidates["Assignment Probability %"].mean()), 2) if not candidates.empty else 0,
        "top_opportunity_score": round(float(candidates["Opportunity Score"].max()), 2) if not candidates.empty else 0,
    }

    return {
        "available": True,
        "summary": summary,
        "candidates": candidates,
        "approved": approved,
        "policy": policy,
    }


def summarize_cash_secured_put_factory(report: dict[str, Any]) -> str:
    if not report.get("available"):
        return f"Cash Secured Put Factory unavailable: {report.get('reason', 'unknown reason')}"

    s = report.get("summary", {})
    return (
        f"Cash Secured Put Factory found {s.get('candidate_count')} candidates, "
        f"with {s.get('approved_count')} approved by policy. "
        f"Average annualized yield is {s.get('avg_annualized_yield')}%, "
        f"average assignment probability is {s.get('avg_assignment_probability')}%, "
        f"and top opportunity score is {s.get('top_opportunity_score')}/100."
    )
