"""
Sprint 10 Phase 3 — Term Structure Intelligence Engine.

Institutional volatility term-structure analytics:
- Expiry curve normalization
- Front/mid/back IV curve construction
- Contango / backwardation classification
- Term slope and curvature analytics
- Calendar-spread opportunity detection
- Front-vol richness / back-vol richness scoring
- Volatility carry diagnostics

This module does not place trades. It generates deterministic term-structure
intelligence for dashboards and future volatility command-center modules.
"""
from __future__ import annotations

from typing import Any
import pandas as pd


DEFAULT_TERM_STRUCTURE_POLICY = {
    "front_dte_max": 21,
    "mid_dte_max": 60,
    "back_dte_min": 61,
    "contango_threshold": 0.05,
    "backwardation_threshold": -0.05,
    "steep_slope_threshold": 0.10,
    "flat_slope_threshold": 0.03,
    "calendar_edge_threshold": 0.05,
    "min_volume": 0,
    "min_open_interest": 0,
}


def _df(data: Any) -> pd.DataFrame:
    if isinstance(data, pd.DataFrame):
        return data.copy()
    if isinstance(data, list):
        return pd.DataFrame(data)
    if isinstance(data, dict):
        if isinstance(data.get("term_structure"), pd.DataFrame):
            return data["term_structure"].copy()
        if isinstance(data.get("expiry_summary"), pd.DataFrame):
            return data["expiry_summary"].copy()
        if isinstance(data.get("surface"), pd.DataFrame):
            return data["surface"].copy()
        if isinstance(data.get("surface_grid"), pd.DataFrame):
            return data["surface_grid"].copy()
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


def normalize_term_structure_chain(chain_data: Any) -> pd.DataFrame:
    df = _extract_chain_rows(chain_data)
    if df.empty:
        return df

    df = df.copy()

    defaults = {
        "expiry": "",
        "dte": 30,
        "type": "",
        "strike": 0,
        "iv": 0,
        "mid": 0,
        "bid": 0,
        "ask": 0,
        "last": 0,
        "volume": 0,
        "open_interest": 0,
        "delta": 0,
        "vega": 0,
        "moneyness_pct": 0,
    }

    for col, default in defaults.items():
        if col not in df.columns:
            df[col] = default

    numeric_cols = [
        "dte",
        "strike",
        "iv",
        "mid",
        "bid",
        "ask",
        "last",
        "volume",
        "open_interest",
        "delta",
        "vega",
        "moneyness_pct",
    ]

    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["iv"] = df["iv"].where(df["iv"] <= 3, df["iv"] / 100)
    df["mid"] = df["mid"].where(df["mid"] > 0, ((df["bid"] + df["ask"]) / 2))
    df["mid"] = df["mid"].where(df["mid"] > 0, df["last"])
    df["type"] = df["type"].fillna("").astype(str).str.lower()

    return df


def classify_term_bucket(dte: float, policy: dict[str, Any] | None = None) -> str:
    policy = policy or DEFAULT_TERM_STRUCTURE_POLICY

    if dte <= policy["front_dte_max"]:
        return "FRONT"
    if dte <= policy["mid_dte_max"]:
        return "MID"
    return "BACK"


def build_expiry_curve(chain_data: Any, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = policy or DEFAULT_TERM_STRUCTURE_POLICY
    df = normalize_term_structure_chain(chain_data)

    if df.empty:
        return {
            "available": False,
            "reason": "No option rows available for term structure.",
            "chain": df,
        }

    df = df[
        (df["volume"] >= float(policy.get("min_volume", 0)))
        & (df["open_interest"] >= float(policy.get("min_open_interest", 0)))
    ].copy()

    if df.empty:
        return {
            "available": False,
            "reason": "No option rows passed term-structure liquidity filters.",
            "chain": df,
        }

    df["term_bucket"] = df["dte"].apply(lambda d: classify_term_bucket(float(d), policy))

    curve = (
        df.groupby(["expiry", "dte"], as_index=False)
        .agg(
            avg_iv=("iv", "mean"),
            median_iv=("iv", "median"),
            min_iv=("iv", "min"),
            max_iv=("iv", "max"),
            contracts=("iv", "size"),
            total_volume=("volume", "sum"),
            total_open_interest=("open_interest", "sum"),
            avg_vega=("vega", "mean"),
        )
        .sort_values("dte")
        .reset_index(drop=True)
    )

    curve["term_bucket"] = curve["dte"].apply(lambda d: classify_term_bucket(float(d), policy))
    curve["iv_change"] = curve["avg_iv"].diff().fillna(0)
    curve["slope_from_front"] = curve["avg_iv"] - float(curve["avg_iv"].iloc[0])
    curve["annualized_carry_proxy"] = (curve["avg_iv"].diff().fillna(0) / curve["dte"].diff().replace(0, 1).fillna(1) * 365).round(4)

    return {
        "available": True,
        "chain": df,
        "expiry_curve": curve,
        "policy": policy,
    }


def classify_term_structure(curve: pd.DataFrame, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = policy or DEFAULT_TERM_STRUCTURE_POLICY

    if not isinstance(curve, pd.DataFrame) or curve.empty:
        return {
            "available": False,
            "term_regime": "UNKNOWN",
            "reason": "No expiry curve available.",
        }

    ordered = curve.sort_values("dte").reset_index(drop=True)
    front_iv = float(ordered["avg_iv"].iloc[0])
    back_iv = float(ordered["avg_iv"].iloc[-1])
    slope = back_iv - front_iv

    if slope >= policy["contango_threshold"]:
        regime = "CONTANGO"
    elif slope <= policy["backwardation_threshold"]:
        regime = "BACKWARDATION"
    else:
        regime = "FLAT"

    if abs(slope) >= policy["steep_slope_threshold"]:
        slope_quality = "STEEP"
    elif abs(slope) <= policy["flat_slope_threshold"]:
        slope_quality = "FLAT"
    else:
        slope_quality = "MODERATE"

    curvature = 0.0
    if len(ordered) >= 3:
        front = float(ordered["avg_iv"].iloc[0])
        mid = float(ordered["avg_iv"].iloc[len(ordered) // 2])
        back = float(ordered["avg_iv"].iloc[-1])
        curvature = mid - ((front + back) / 2)

    if curvature > 0.03:
        curvature_regime = "HUMPED"
    elif curvature < -0.03:
        curvature_regime = "DEPRESSED_MID"
    else:
        curvature_regime = "SMOOTH"

    return {
        "available": True,
        "term_regime": regime,
        "slope_quality": slope_quality,
        "front_iv": round(front_iv, 4),
        "back_iv": round(back_iv, 4),
        "term_slope": round(slope, 4),
        "curvature": round(curvature, 4),
        "curvature_regime": curvature_regime,
    }


def build_bucket_summary(chain: pd.DataFrame, policy: dict[str, Any] | None = None) -> pd.DataFrame:
    policy = policy or DEFAULT_TERM_STRUCTURE_POLICY

    if chain.empty:
        return pd.DataFrame()

    table = (
        chain.groupby("term_bucket", as_index=False)
        .agg(
            avg_iv=("iv", "mean"),
            contracts=("iv", "size"),
            total_volume=("volume", "sum"),
            total_open_interest=("open_interest", "sum"),
            avg_dte=("dte", "mean"),
            avg_vega=("vega", "mean"),
        )
        .reset_index(drop=True)
    )

    order = {"FRONT": 0, "MID": 1, "BACK": 2}
    table["_sort"] = table["term_bucket"].map(order).fillna(9)
    table = table.sort_values("_sort").drop(columns=["_sort"]).reset_index(drop=True)

    for col in ["avg_iv", "avg_dte", "avg_vega"]:
        table[col] = pd.to_numeric(table[col], errors="coerce").fillna(0).round(4)

    return table


def find_calendar_opportunities(
    curve: pd.DataFrame,
    term_state: dict[str, Any],
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or DEFAULT_TERM_STRUCTURE_POLICY

    if not isinstance(curve, pd.DataFrame) or curve.empty:
        return {
            "available": False,
            "reason": "No expiry curve available for calendar scan.",
            "opportunities": pd.DataFrame(),
        }

    rows = []
    ordered = curve.sort_values("dte").reset_index(drop=True)
    regime = term_state.get("term_regime", "UNKNOWN")

    for i in range(len(ordered) - 1):
        front = ordered.iloc[i]
        back = ordered.iloc[i + 1]
        spread = float(back["avg_iv"] - front["avg_iv"])

        if spread >= policy["calendar_edge_threshold"]:
            rows.append({
                "Opportunity": "Long Calendar / Long Back Vol",
                "Front Expiry": front["expiry"],
                "Back Expiry": back["expiry"],
                "Front DTE": front["dte"],
                "Back DTE": back["dte"],
                "Front IV": round(float(front["avg_iv"]), 4),
                "Back IV": round(float(back["avg_iv"]), 4),
                "IV Spread": round(spread, 4),
                "Priority": "High" if spread >= policy["steep_slope_threshold"] else "Normal",
                "Rationale": "Back expiry IV is materially above front expiry IV.",
            })

        if spread <= -policy["calendar_edge_threshold"]:
            rows.append({
                "Opportunity": "Short Front-Rich Vol / Reverse Calendar Review",
                "Front Expiry": front["expiry"],
                "Back Expiry": back["expiry"],
                "Front DTE": front["dte"],
                "Back DTE": back["dte"],
                "Front IV": round(float(front["avg_iv"]), 4),
                "Back IV": round(float(back["avg_iv"]), 4),
                "IV Spread": round(spread, 4),
                "Priority": "High",
                "Rationale": "Front expiry IV is materially rich versus next expiry.",
            })

    if not rows:
        if regime == "CONTANGO":
            rows.append({
                "Opportunity": "Balanced Calendar Watchlist",
                "Front Expiry": "",
                "Back Expiry": "",
                "Front DTE": 0,
                "Back DTE": 0,
                "Front IV": term_state.get("front_iv", 0),
                "Back IV": term_state.get("back_iv", 0),
                "IV Spread": term_state.get("term_slope", 0),
                "Priority": "Normal",
                "Rationale": "Term structure is in contango, but no adjacent expiry spread exceeds edge threshold.",
            })
        elif regime == "BACKWARDATION":
            rows.append({
                "Opportunity": "Front Vol Risk Review",
                "Front Expiry": "",
                "Back Expiry": "",
                "Front DTE": 0,
                "Back DTE": 0,
                "Front IV": term_state.get("front_iv", 0),
                "Back IV": term_state.get("back_iv", 0),
                "IV Spread": term_state.get("term_slope", 0),
                "Priority": "High",
                "Rationale": "Backwardation suggests front-vol stress.",
            })

    return {
        "available": True,
        "opportunities": pd.DataFrame(rows),
    }


def generate_term_structure_recommendations(term_state: dict[str, Any], opportunities: dict[str, Any]) -> pd.DataFrame:
    regime = term_state.get("term_regime", "UNKNOWN")
    curvature = term_state.get("curvature_regime", "UNKNOWN")
    rows = []

    if regime == "CONTANGO":
        rows.append({
            "Recommendation": "Evaluate Long Calendar Structures",
            "Priority": "Normal",
            "Rationale": "Back expiries are priced above front expiries.",
            "Candidate Structures": "Calendars, diagonals, longer-dated hedges",
        })

    elif regime == "BACKWARDATION":
        rows.append({
            "Recommendation": "Review Front-Vol Richness",
            "Priority": "High",
            "Rationale": "Front expiry IV is elevated versus back expiry IV.",
            "Candidate Structures": "Front premium harvest, reverse calendars, event-risk hedges",
        })

    else:
        rows.append({
            "Recommendation": "Neutral Term Structure",
            "Priority": "Normal",
            "Rationale": "Front and back implied volatility are broadly aligned.",
            "Candidate Structures": "Defined-risk spreads, balanced volatility structures",
        })

    if curvature == "HUMPED":
        rows.append({
            "Recommendation": "Mid-Curve Richness Review",
            "Priority": "Medium",
            "Rationale": "Mid-expiry IV is rich relative to front/back curve.",
            "Candidate Structures": "Butterfly calendars, mid-curve spreads",
        })

    elif curvature == "DEPRESSED_MID":
        rows.append({
            "Recommendation": "Mid-Curve Cheapness Review",
            "Priority": "Medium",
            "Rationale": "Mid-expiry IV is cheap relative to front/back curve.",
            "Candidate Structures": "Long mid-expiry calendars, diagonal structures",
        })

    opp_df = opportunities.get("opportunities")
    if isinstance(opp_df, pd.DataFrame) and not opp_df.empty:
        rows.append({
            "Recommendation": "Work Calendar Opportunity Queue",
            "Priority": "High" if "High" in set(opp_df["Priority"].astype(str)) else "Normal",
            "Rationale": f"{len(opp_df)} calendar / term opportunities detected.",
            "Candidate Structures": "See opportunity queue",
        })

    return pd.DataFrame(rows)


def build_term_structure_report(chain_data: Any, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = policy or DEFAULT_TERM_STRUCTURE_POLICY

    base = build_expiry_curve(chain_data, policy=policy)
    if not base.get("available"):
        return base

    curve = base.get("expiry_curve")
    chain = base.get("chain")

    term_state = classify_term_structure(curve, policy=policy)
    buckets = build_bucket_summary(chain, policy=policy)
    opportunities = find_calendar_opportunities(curve, term_state, policy=policy)
    recommendations = generate_term_structure_recommendations(term_state, opportunities)

    summary = {
        "term_regime": term_state.get("term_regime", "UNKNOWN"),
        "slope_quality": term_state.get("slope_quality", "UNKNOWN"),
        "front_iv": term_state.get("front_iv", 0),
        "back_iv": term_state.get("back_iv", 0),
        "term_slope": term_state.get("term_slope", 0),
        "curvature": term_state.get("curvature", 0),
        "curvature_regime": term_state.get("curvature_regime", "UNKNOWN"),
        "expiry_count": int(len(curve)) if isinstance(curve, pd.DataFrame) else 0,
        "opportunity_count": int(len(opportunities.get("opportunities", pd.DataFrame()))) if opportunities.get("available") else 0,
    }

    return {
        "available": True,
        "summary": summary,
        "chain": chain,
        "expiry_curve": curve,
        "bucket_summary": buckets,
        "term_state": term_state,
        "opportunities": opportunities,
        "recommendations": recommendations,
        "policy": policy,
    }


def summarize_term_structure(report: dict[str, Any]) -> str:
    if not report.get("available"):
        return f"Term Structure Intelligence unavailable: {report.get('reason', 'unknown reason')}"

    s = report.get("summary", {})
    return (
        f"Term Structure is {s.get('term_regime')} with {s.get('slope_quality')} slope. "
        f"Front IV is {s.get('front_iv')}, back IV is {s.get('back_iv')}, "
        f"and term slope is {s.get('term_slope')}. "
        f"Curvature regime is {s.get('curvature_regime')}. "
        f"{s.get('opportunity_count')} term-structure opportunities were identified."
    )
