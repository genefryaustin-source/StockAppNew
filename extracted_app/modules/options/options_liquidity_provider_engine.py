"""
Sprint 11 Phase 4 — Liquidity Provider Intelligence Engine.

Institutional market-making analytics:
- Options liquidity provider quality scoring
- Bid/ask spread diagnostics
- Depth proxy using volume/open interest
- Market-maker participation proxy
- Liquidity stress detection
- Sweep/impact risk proxy
- Strike/expiry liquidity maps
- Execution routing guidance

This module does not place trades. It creates deterministic liquidity-provider
diagnostics from options-chain data.
"""
from __future__ import annotations

from typing import Any
import pandas as pd


DEFAULT_LP_POLICY = {
    "tight_spread_pct": 0.05,
    "wide_spread_pct": 0.20,
    "minimum_volume": 10,
    "minimum_open_interest": 100,
    "high_volume": 500,
    "high_open_interest": 1000,
    "stress_spread_pct": 0.35,
    "illiquid_score_threshold": 40,
    "strong_score_threshold": 75,
}


def _df(data: Any) -> pd.DataFrame:
    if isinstance(data, pd.DataFrame):
        return data.copy()
    if isinstance(data, list):
        return pd.DataFrame(data)
    if isinstance(data, dict):
        if isinstance(data.get("all_rows"), pd.DataFrame):
            return data["all_rows"].copy()
        if isinstance(data.get("data"), pd.DataFrame):
            return data["data"].copy()
        rows = []
        if isinstance(data.get("calls"), pd.DataFrame):
            calls = data["calls"].copy()
            calls["type"] = calls.get("type", "call")
            rows.append(calls)
        if isinstance(data.get("puts"), pd.DataFrame):
            puts = data["puts"].copy()
            puts["type"] = puts.get("type", "put")
            rows.append(puts)
        if rows:
            return pd.concat(rows, ignore_index=True)
    return pd.DataFrame()


def _extract_chain_rows(chain_data: Any) -> pd.DataFrame:
    if isinstance(chain_data, dict) and isinstance(chain_data.get("chain"), dict):
        rows = []
        for expiry, payload in chain_data["chain"].items():
            if not isinstance(payload, dict):
                continue
            for key, opt_type in [("calls", "call"), ("puts", "put")]:
                block = payload.get(key)
                if isinstance(block, pd.DataFrame) and not block.empty:
                    temp = block.copy()
                    temp["expiry"] = temp.get("expiry", expiry)
                    temp["type"] = opt_type
                    rows.append(temp)
        if rows:
            return pd.concat(rows, ignore_index=True)
    return _df(chain_data)


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def normalize_liquidity_provider_chain(chain_data: Any) -> pd.DataFrame:
    df = _extract_chain_rows(chain_data)
    if df.empty:
        return df

    df = df.copy()

    defaults = {
        "underlying": "",
        "symbol": "",
        "option_symbol": "",
        "expiry": "",
        "type": "",
        "strike": 0,
        "bid": 0,
        "ask": 0,
        "last": 0,
        "mid": 0,
        "volume": 0,
        "open_interest": 0,
        "iv": 0,
        "delta": 0,
        "gamma": 0,
        "theta": 0,
        "vega": 0,
        "dte": 30,
    }

    for col, default in defaults.items():
        if col not in df.columns:
            df[col] = default

    for col in [
        "strike", "bid", "ask", "last", "mid", "volume", "open_interest",
        "iv", "delta", "gamma", "theta", "vega", "dte",
    ]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["type"] = df["type"].fillna("").astype(str).str.lower()
    df["iv"] = df["iv"].where(df["iv"] <= 3, df["iv"] / 100)

    df["mid"] = df["mid"].where(df["mid"] > 0, ((df["bid"] + df["ask"]) / 2))
    df["mid"] = df["mid"].where(df["mid"] > 0, df["last"])
    df["spread"] = (df["ask"] - df["bid"]).where((df["ask"] > 0) & (df["bid"] > 0), 0)
    df["spread_pct"] = (df["spread"] / df["mid"].replace(0, 1)).clip(lower=0)

    return df


def score_liquidity_row(row: pd.Series, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = policy or DEFAULT_LP_POLICY

    spread_pct = _num(row.get("spread_pct"), 0)
    volume = _num(row.get("volume"), 0)
    oi = _num(row.get("open_interest"), 0)
    bid = _num(row.get("bid"), 0)
    ask = _num(row.get("ask"), 0)
    mid = _num(row.get("mid"), 0)

    score = 50.0
    flags = []

    if bid <= 0 or ask <= 0 or mid <= 0:
        score -= 35
        flags.append("Quote quality is weak or incomplete.")
    elif spread_pct <= policy["tight_spread_pct"]:
        score += 20
        flags.append("Bid/ask spread is tight.")
    elif spread_pct >= policy["wide_spread_pct"]:
        score -= 25
        flags.append("Bid/ask spread is wide.")
    else:
        score += 5
        flags.append("Bid/ask spread is acceptable.")

    if volume >= policy["high_volume"]:
        score += 15
        flags.append("Volume is strong.")
    elif volume >= policy["minimum_volume"]:
        score += 5
        flags.append("Volume is acceptable.")
    else:
        score -= 12
        flags.append("Volume is thin.")

    if oi >= policy["high_open_interest"]:
        score += 15
        flags.append("Open interest is strong.")
    elif oi >= policy["minimum_open_interest"]:
        score += 5
        flags.append("Open interest is acceptable.")
    else:
        score -= 12
        flags.append("Open interest is thin.")

    if spread_pct >= policy["stress_spread_pct"]:
        score -= 20
        flags.append("Liquidity stress spread detected.")

    score = round(max(0, min(100, score)), 2)

    if score >= policy["strong_score_threshold"]:
        quality = "STRONG"
    elif score >= 60:
        quality = "GOOD"
    elif score >= policy["illiquid_score_threshold"]:
        quality = "WATCH"
    else:
        quality = "ILLIQUID"

    if quality in {"STRONG", "GOOD"}:
        routing = "Limit order near mid; standard execution acceptable."
    elif quality == "WATCH":
        routing = "Use patient limit order; avoid market order."
    else:
        routing = "Avoid or size very small; liquidity is poor."

    return {
        "Liquidity Provider Score": score,
        "Liquidity Quality": quality,
        "Execution Guidance": routing,
        "Liquidity Flags": "; ".join(flags) if flags else "No major liquidity flags.",
    }


def build_liquidity_provider_map(chain_data: Any, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = policy or DEFAULT_LP_POLICY
    df = normalize_liquidity_provider_chain(chain_data)

    if df.empty:
        return {
            "available": False,
            "reason": "No option rows available for liquidity provider intelligence.",
            "chain": df,
        }

    scored = pd.DataFrame([score_liquidity_row(row, policy) for _, row in df.iterrows()])
    enriched = pd.concat([df.reset_index(drop=True), scored.reset_index(drop=True)], axis=1)

    by_expiry = (
        enriched.groupby(["expiry", "dte"], as_index=False)
        .agg(
            avg_liquidity_score=("Liquidity Provider Score", "mean"),
            avg_spread_pct=("spread_pct", "mean"),
            contracts=("Liquidity Provider Score", "size"),
            total_volume=("volume", "sum"),
            total_open_interest=("open_interest", "sum"),
            illiquid_contracts=("Liquidity Quality", lambda s: int((s == "ILLIQUID").sum())),
            strong_contracts=("Liquidity Quality", lambda s: int((s == "STRONG").sum())),
        )
        .sort_values("dte")
        .reset_index(drop=True)
    )

    by_strike = (
        enriched.groupby("strike", as_index=False)
        .agg(
            avg_liquidity_score=("Liquidity Provider Score", "mean"),
            avg_spread_pct=("spread_pct", "mean"),
            contracts=("Liquidity Provider Score", "size"),
            total_volume=("volume", "sum"),
            total_open_interest=("open_interest", "sum"),
        )
        .sort_values("strike")
        .reset_index(drop=True)
    )

    for table in [by_expiry, by_strike]:
        for col in ["avg_liquidity_score", "avg_spread_pct"]:
            if col in table.columns:
                table[col] = pd.to_numeric(table[col], errors="coerce").fillna(0).round(4)

    return {
        "available": True,
        "chain": enriched,
        "by_expiry": by_expiry,
        "by_strike": by_strike,
        "policy": policy,
    }


def classify_liquidity_provider_regime(lp_report: dict[str, Any], policy: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = policy or DEFAULT_LP_POLICY

    if not lp_report.get("available"):
        return lp_report

    df = lp_report.get("chain")
    if not isinstance(df, pd.DataFrame) or df.empty:
        return {"available": False, "reason": "No liquidity chain available."}

    avg_score = float(df["Liquidity Provider Score"].mean())
    avg_spread = float(df["spread_pct"].mean())
    illiquid_count = int((df["Liquidity Quality"] == "ILLIQUID").sum())
    strong_count = int((df["Liquidity Quality"] == "STRONG").sum())
    watch_count = int((df["Liquidity Quality"] == "WATCH").sum())

    stress_count = int((df["spread_pct"] >= policy["stress_spread_pct"]).sum())

    drivers = []

    if avg_score >= policy["strong_score_threshold"]:
        regime = "DEEP_LIQUIDITY"
        drivers.append("Average liquidity provider score is strong.")
    elif avg_score >= 60:
        regime = "NORMAL_LIQUIDITY"
        drivers.append("Average liquidity provider score is acceptable.")
    elif avg_score >= policy["illiquid_score_threshold"]:
        regime = "THIN_LIQUIDITY"
        drivers.append("Liquidity is thin and requires patient execution.")
    else:
        regime = "STRESSED_LIQUIDITY"
        drivers.append("Liquidity conditions are poor.")

    if stress_count > 0:
        drivers.append(f"{stress_count} contracts show stressed spreads.")

    if illiquid_count > strong_count:
        drivers.append("Illiquid contracts outnumber strong-liquidity contracts.")

    return {
        "available": True,
        "liquidity_regime": regime,
        "avg_liquidity_score": round(avg_score, 2),
        "avg_spread_pct": round(avg_spread, 4),
        "illiquid_count": illiquid_count,
        "watch_count": watch_count,
        "strong_count": strong_count,
        "stress_count": stress_count,
        "drivers": drivers or ["Liquidity conditions are balanced."],
    }


def build_liquidity_provider_opportunities(lp_report: dict[str, Any], regime: dict[str, Any]) -> pd.DataFrame:
    if not lp_report.get("available"):
        return pd.DataFrame()

    df = lp_report.get("chain")
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()

    rows = []

    best = df[df["Liquidity Quality"].isin(["STRONG", "GOOD"])].sort_values(
        ["Liquidity Provider Score", "volume", "open_interest"],
        ascending=False,
    ).head(20)

    for _, row in best.iterrows():
        rows.append({
            "Opportunity": "High-Quality Liquidity",
            "Priority": "Normal",
            "Option": row.get("option_symbol", ""),
            "Expiry": row.get("expiry", ""),
            "Type": row.get("type", ""),
            "Strike": row.get("strike", 0),
            "Liquidity Score": row.get("Liquidity Provider Score", 0),
            "Spread %": row.get("spread_pct", 0),
            "Guidance": row.get("Execution Guidance", ""),
        })

    stressed = df[df["Liquidity Quality"].eq("ILLIQUID")].sort_values(
        ["spread_pct", "open_interest"],
        ascending=[False, True],
    ).head(20)

    for _, row in stressed.iterrows():
        rows.append({
            "Opportunity": "Avoid / Execution Risk",
            "Priority": "High",
            "Option": row.get("option_symbol", ""),
            "Expiry": row.get("expiry", ""),
            "Type": row.get("type", ""),
            "Strike": row.get("strike", 0),
            "Liquidity Score": row.get("Liquidity Provider Score", 0),
            "Spread %": row.get("spread_pct", 0),
            "Guidance": row.get("Execution Guidance", ""),
        })

    return pd.DataFrame(rows)


def generate_liquidity_provider_recommendations(regime: dict[str, Any]) -> pd.DataFrame:
    liquidity_regime = regime.get("liquidity_regime", "UNKNOWN")
    rows = []

    if liquidity_regime == "DEEP_LIQUIDITY":
        rows.append({
            "Recommendation": "Standard Liquidity Conditions",
            "Priority": "Normal",
            "Rationale": "Liquidity provider quality is strong.",
            "Execution Playbook": "Use limit orders near mid; larger sizes may be acceptable.",
        })
    elif liquidity_regime == "NORMAL_LIQUIDITY":
        rows.append({
            "Recommendation": "Normal Liquidity With Limit Orders",
            "Priority": "Normal",
            "Rationale": "Liquidity is acceptable but should still use controlled order placement.",
            "Execution Playbook": "Use limit orders; avoid crossing wide spreads.",
        })
    elif liquidity_regime == "THIN_LIQUIDITY":
        rows.append({
            "Recommendation": "Patient Execution Required",
            "Priority": "Medium",
            "Rationale": "Liquidity is thin.",
            "Execution Playbook": "Scale into orders, use price improvement, reduce size.",
        })
    else:
        rows.append({
            "Recommendation": "Liquidity Stress / Avoid Market Orders",
            "Priority": "High",
            "Rationale": "Liquidity is stressed or unreliable.",
            "Execution Playbook": "Avoid market orders, use very small size or avoid trade.",
        })

    if regime.get("stress_count", 0) > 0:
        rows.append({
            "Recommendation": "Review Stressed Contracts",
            "Priority": "High",
            "Rationale": f"{regime.get('stress_count')} contracts have stressed spreads.",
            "Execution Playbook": "Avoid low-quality contracts unless liquidity improves.",
        })

    return pd.DataFrame(rows)


def build_liquidity_provider_report(chain_data: Any, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = policy or DEFAULT_LP_POLICY

    lp_map = build_liquidity_provider_map(chain_data, policy=policy)
    if not lp_map.get("available"):
        return lp_map

    regime = classify_liquidity_provider_regime(lp_map, policy=policy)
    opportunities = build_liquidity_provider_opportunities(lp_map, regime)
    recommendations = generate_liquidity_provider_recommendations(regime)

    summary = {
        "liquidity_regime": regime.get("liquidity_regime"),
        "avg_liquidity_score": regime.get("avg_liquidity_score"),
        "avg_spread_pct": regime.get("avg_spread_pct"),
        "illiquid_count": regime.get("illiquid_count"),
        "watch_count": regime.get("watch_count"),
        "strong_count": regime.get("strong_count"),
        "stress_count": regime.get("stress_count"),
        "contract_count": int(len(lp_map.get("chain", pd.DataFrame()))),
        "opportunity_count": int(len(opportunities)),
    }

    return {
        "available": True,
        "summary": summary,
        "lp_map": lp_map,
        "regime": regime,
        "opportunities": opportunities,
        "recommendations": recommendations,
        "policy": policy,
    }


def summarize_liquidity_provider(report: dict[str, Any]) -> str:
    if not report.get("available"):
        return f"Liquidity Provider Intelligence unavailable: {report.get('reason', 'unknown reason')}"

    s = report.get("summary", {})
    return (
        f"Liquidity Provider regime is {s.get('liquidity_regime')} with average score "
        f"{s.get('avg_liquidity_score')}/100 and average spread {s.get('avg_spread_pct')}. "
        f"{s.get('strong_count')} strong contracts, {s.get('watch_count')} watch contracts, "
        f"and {s.get('illiquid_count')} illiquid contracts were detected."
    )
