"""
Sprint 6 Phase 2 — Liquidity Intelligence Engine.

Institutional liquidity diagnostics for option chains:
- Bid/ask spread quality
- Open interest quality
- Volume quality
- Tradability score
- Institutional capacity estimate
- Recommended order size
- Liquidity heatmap tables
- Execution difficulty classification

Consumes existing chain_data from get_options_chain(ticker).
"""
from __future__ import annotations

from typing import Any
import pandas as pd


def _as_frame(data: Any) -> pd.DataFrame:
    if data is None:
        return pd.DataFrame()
    if isinstance(data, pd.DataFrame):
        return data.copy()
    if isinstance(data, list):
        return pd.DataFrame(data)
    return pd.DataFrame()


def _num(series: pd.Series, default: float = 0.0) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(default)

def calculate_liquidity_score(
    chain_data,
    selected_expiry=None,
    *args,
    **kwargs
):
    """
    Backward-compatible liquidity scoring.

    Parameters
    ----------
    chain_data : dict | DataFrame
    selected_expiry : str | None
    """

    report = analyze_chain_liquidity(chain_data)

    if not report.get("available"):
        return {
            "score": 0,
            "grade": "N/A",
            "summary": report.get("reason", "No liquidity data"),
        }

    summary = report.get("summary", {})

    return {
        "score": summary.get("avg_liquidity_score", 0),
        "grade": summary.get("market_liquidity_grade", "N/A"),
        "liquid_contracts": summary.get("liquid_contracts", 0),
        "tradable_contracts": summary.get("tradable_contracts", 0),
        "avg_spread_pct": summary.get("avg_spread_pct", 0),
        "total_volume": summary.get("total_volume", 0),
        "total_open_interest": summary.get("total_open_interest", 0),
    }

def summarize_liquidity(chain_data):
    """
    Backward compatibility wrapper for older dashboards.
    """

    report = analyze_chain_liquidity(chain_data)

    if not report.get("available"):
        return report.get(
            "reason",
            "No liquidity data available."
        )

    return summarize_liquidity_intelligence(report)

def _extract_chain_rows(chain_data: Any) -> pd.DataFrame:
    if chain_data is None:
        return pd.DataFrame()

    if isinstance(chain_data, pd.DataFrame):
        return chain_data.copy()

    if isinstance(chain_data, dict):
        if isinstance(chain_data.get("all_rows"), pd.DataFrame):
            return chain_data["all_rows"].copy()

        rows = []
        chain = chain_data.get("chain", {})
        if isinstance(chain, dict):
            for expiry, payload in chain.items():
                if not isinstance(payload, dict):
                    continue
                for side_key, opt_type in [("calls", "call"), ("puts", "put")]:
                    df = payload.get(side_key)
                    if isinstance(df, pd.DataFrame) and not df.empty:
                        temp = df.copy()
                        temp["expiry"] = temp.get("expiry", expiry)
                        temp["type"] = temp.get("type", opt_type)
                        rows.append(temp)
        if rows:
            return pd.concat(rows, ignore_index=True)

    return pd.DataFrame()


def normalize_liquidity_chain(chain_data: Any) -> pd.DataFrame:
    df = _extract_chain_rows(chain_data)
    if df.empty:
        return df

    df = df.copy()

    defaults = {
        "option_symbol": "",
        "expiry": "",
        "type": "",
        "strike": 0,
        "bid": 0,
        "ask": 0,
        "last": 0,
        "volume": 0,
        "open_interest": 0,
        "iv": 0,
        "delta": 0,
        "gamma": 0,
        "theta": 0,
        "vega": 0,
        "dte": 0,
    }

    for col, default in defaults.items():
        if col not in df.columns:
            df[col] = default

    for col in ["strike", "bid", "ask", "last", "volume", "open_interest", "iv", "delta", "gamma", "theta", "vega", "dte"]:
        df[col] = _num(df[col])

    df["type"] = df["type"].fillna("").astype(str).str.lower()
    df["expiry"] = df["expiry"].fillna("").astype(str)
    df["option_symbol"] = df["option_symbol"].fillna("").astype(str)

    df["mid"] = ((df["bid"] + df["ask"]) / 2).where((df["bid"] > 0) & (df["ask"] > 0), df["last"])
    df["spread"] = (df["ask"] - df["bid"]).where((df["ask"] > 0) & (df["bid"] > 0), 0)
    df["spread_pct"] = (df["spread"] / df["mid"].replace(0, 1)).clip(lower=0)

    df["dollar_volume"] = df["volume"] * df["mid"] * 100
    df["oi_notional"] = df["open_interest"] * df["mid"] * 100

    return df


def _score_spread(spread_pct: float) -> float:
    if spread_pct <= 0:
        return 30
    if spread_pct <= 0.02:
        return 100
    if spread_pct <= 0.05:
        return 85
    if spread_pct <= 0.10:
        return 65
    if spread_pct <= 0.20:
        return 45
    return 20


def _score_volume(volume: float) -> float:
    if volume >= 5000:
        return 100
    if volume >= 1000:
        return 85
    if volume >= 250:
        return 65
    if volume >= 50:
        return 45
    if volume > 0:
        return 25
    return 10


def _score_open_interest(oi: float) -> float:
    if oi >= 10000:
        return 100
    if oi >= 2500:
        return 85
    if oi >= 500:
        return 65
    if oi >= 100:
        return 45
    if oi > 0:
        return 25
    return 10


def score_contract_liquidity(row: pd.Series) -> dict[str, Any]:
    spread_score = _score_spread(float(row.get("spread_pct") or 0))
    volume_score = _score_volume(float(row.get("volume") or 0))
    oi_score = _score_open_interest(float(row.get("open_interest") or 0))

    score = round(
        spread_score * 0.45
        + volume_score * 0.30
        + oi_score * 0.25,
        2,
    )

    if score >= 85:
        grade = "A"
        difficulty = "LOW"
    elif score >= 70:
        grade = "B"
        difficulty = "LOW_MEDIUM"
    elif score >= 55:
        grade = "C"
        difficulty = "MEDIUM"
    elif score >= 40:
        grade = "D"
        difficulty = "HIGH"
    else:
        grade = "F"
        difficulty = "VERY_HIGH"

    mid = float(row.get("mid") or 0)
    volume = float(row.get("volume") or 0)
    oi = float(row.get("open_interest") or 0)

    # Conservative capacity estimate: lower of 5% OI and 10% daily volume.
    cap_contracts = max(1, int(max(0, min(oi * 0.05, volume * 0.10)) or 1))
    cap_notional = cap_contracts * mid * 100

    # Recommended order size tiers.
    if score >= 85:
        recommended_order = cap_contracts
    elif score >= 70:
        recommended_order = max(1, int(cap_contracts * 0.75))
    elif score >= 55:
        recommended_order = max(1, int(cap_contracts * 0.50))
    else:
        recommended_order = max(1, int(cap_contracts * 0.25))

    return {
        "liquidity_score": score,
        "liquidity_grade": grade,
        "execution_difficulty": difficulty,
        "spread_score": round(spread_score, 2),
        "volume_score": round(volume_score, 2),
        "open_interest_score": round(oi_score, 2),
        "capacity_contracts": int(cap_contracts),
        "capacity_notional": round(cap_notional, 2),
        "recommended_order_contracts": int(recommended_order),
    }


def analyze_chain_liquidity(chain_data: Any) -> dict[str, Any]:
    df = normalize_liquidity_chain(chain_data)
    if df.empty:
        return {"available": False, "reason": "No options chain data available.", "contracts": df}

    scores = pd.DataFrame([score_contract_liquidity(row) for _, row in df.iterrows()])
    enriched = pd.concat([df.reset_index(drop=True), scores.reset_index(drop=True)], axis=1)

    avg_score = round(float(enriched["liquidity_score"].mean()), 2)
    median_score = round(float(enriched["liquidity_score"].median()), 2)
    liquid_count = int((enriched["liquidity_score"] >= 70).sum())
    tradable_count = int((enriched["liquidity_score"] >= 55).sum())

    if avg_score >= 85:
        market_grade = "A"
    elif avg_score >= 70:
        market_grade = "B"
    elif avg_score >= 55:
        market_grade = "C"
    elif avg_score >= 40:
        market_grade = "D"
    else:
        market_grade = "F"

    return {
        "available": True,
        "contracts": enriched,
        "summary": {
            "contract_count": int(len(enriched)),
            "avg_liquidity_score": avg_score,
            "median_liquidity_score": median_score,
            "market_liquidity_grade": market_grade,
            "liquid_contracts": liquid_count,
            "tradable_contracts": tradable_count,
            "avg_spread_pct": round(float(enriched["spread_pct"].mean() * 100), 2),
            "total_volume": int(enriched["volume"].sum()),
            "total_open_interest": int(enriched["open_interest"].sum()),
            "total_dollar_volume": round(float(enriched["dollar_volume"].sum()), 2),
            "total_oi_notional": round(float(enriched["oi_notional"].sum()), 2),
        },
    }


def build_liquidity_by_expiry(chain_data: Any) -> dict[str, Any]:
    report = analyze_chain_liquidity(chain_data)
    if not report.get("available"):
        return report

    df = report["contracts"]
    table = (
        df.groupby("expiry", as_index=False)
        .agg(
            contracts=("expiry", "size"),
            avg_score=("liquidity_score", "mean"),
            avg_spread_pct=("spread_pct", "mean"),
            volume=("volume", "sum"),
            open_interest=("open_interest", "sum"),
            dollar_volume=("dollar_volume", "sum"),
            oi_notional=("oi_notional", "sum"),
            liquid_contracts=("liquidity_score", lambda s: int((s >= 70).sum())),
        )
        .sort_values("volume", ascending=False)
        .reset_index(drop=True)
    )
    table["avg_score"] = table["avg_score"].round(2)
    table["avg_spread_pct"] = (table["avg_spread_pct"] * 100).round(2)
    table["dollar_volume"] = table["dollar_volume"].round(2)
    table["oi_notional"] = table["oi_notional"].round(2)

    return {"available": True, "by_expiry": table}


def build_liquidity_by_strike(chain_data: Any) -> dict[str, Any]:
    report = analyze_chain_liquidity(chain_data)
    if not report.get("available"):
        return report

    df = report["contracts"]
    table = (
        df.groupby(["strike", "type"], as_index=False)
        .agg(
            contracts=("strike", "size"),
            avg_score=("liquidity_score", "mean"),
            avg_spread_pct=("spread_pct", "mean"),
            volume=("volume", "sum"),
            open_interest=("open_interest", "sum"),
            dollar_volume=("dollar_volume", "sum"),
            oi_notional=("oi_notional", "sum"),
        )
        .sort_values(["avg_score", "volume"], ascending=False)
        .reset_index(drop=True)
    )
    table["avg_score"] = table["avg_score"].round(2)
    table["avg_spread_pct"] = (table["avg_spread_pct"] * 100).round(2)
    table["dollar_volume"] = table["dollar_volume"].round(2)
    table["oi_notional"] = table["oi_notional"].round(2)

    return {"available": True, "by_strike": table}


def find_best_liquidity_contracts(chain_data: Any, limit: int = 25) -> dict[str, Any]:
    report = analyze_chain_liquidity(chain_data)
    if not report.get("available"):
        return report

    df = report["contracts"]
    cols = [
        "option_symbol",
        "expiry",
        "type",
        "strike",
        "bid",
        "ask",
        "mid",
        "spread",
        "spread_pct",
        "volume",
        "open_interest",
        "liquidity_score",
        "liquidity_grade",
        "execution_difficulty",
        "capacity_contracts",
        "recommended_order_contracts",
    ]

    best = (
        df.sort_values(["liquidity_score", "volume", "open_interest"], ascending=False)
        [[c for c in cols if c in df.columns]]
        .head(limit)
        .reset_index(drop=True)
    )
    best["spread_pct"] = (best["spread_pct"] * 100).round(2)

    return {"available": True, "best_contracts": best}


def build_liquidity_intelligence_report(chain_data: Any) -> dict[str, Any]:
    base = analyze_chain_liquidity(chain_data)
    if not base.get("available"):
        return base

    by_expiry = build_liquidity_by_expiry(chain_data)
    by_strike = build_liquidity_by_strike(chain_data)
    best = find_best_liquidity_contracts(chain_data)

    return {
        **base,
        "by_expiry": by_expiry,
        "by_strike": by_strike,
        "best_contracts": best,
    }


def summarize_liquidity_intelligence(report: dict[str, Any]) -> str:
    if not report.get("available"):
        return f"Liquidity intelligence unavailable: {report.get('reason', 'unknown reason')}"

    summary = report.get("summary", {})
    return (
        f"Options chain liquidity grade is {summary.get('market_liquidity_grade')} "
        f"with average score {summary.get('avg_liquidity_score')}/100. "
        f"{summary.get('liquid_contracts')} contracts are highly liquid and "
        f"{summary.get('tradable_contracts')} are tradable. Average spread is "
        f"{summary.get('avg_spread_pct')}%."
    )
