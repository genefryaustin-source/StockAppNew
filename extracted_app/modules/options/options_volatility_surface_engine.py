"""
Sprint 10 Phase 1 — Volatility Surface Intelligence Engine.
"""
from __future__ import annotations

from typing import Any
import math
import pandas as pd


DEFAULT_SURFACE_POLICY = {
    "atm_moneyness_band_pct": 5.0,
    "wing_moneyness_band_pct": 15.0,
    "high_iv_threshold": 0.60,
    "low_iv_threshold": 0.20,
    "steep_skew_threshold": 0.10,
    "term_inversion_threshold": 0.05,
    "min_volume": 0,
    "min_open_interest": 0,
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


def normalize_surface_chain(chain_data: Any, underlying_price: float | None = None) -> pd.DataFrame:
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
        "underlying_price": 0,
        "spot": 0,
        "last_underlying_price": 0,
    }

    for col, default in defaults.items():
        if col not in df.columns:
            df[col] = default

    for col in [
        "strike", "bid", "ask", "last", "mid", "volume", "open_interest",
        "iv", "delta", "gamma", "theta", "vega", "dte",
        "underlying_price", "spot", "last_underlying_price",
    ]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["mid"] = df["mid"].where(df["mid"] > 0, ((df["bid"] + df["ask"]) / 2))
    df["mid"] = df["mid"].where(df["mid"] > 0, df["last"])

    spot = underlying_price or 0
    if spot <= 0:
        for col in ["underlying_price", "spot", "last_underlying_price", "strike"]:
            vals = df[col].replace(0, pd.NA).dropna()
            if not vals.empty:
                spot = float(vals.median())
                break
    if spot <= 0:
        spot = 1.0

    df["surface_underlying_price"] = float(spot)
    df["moneyness"] = (df["strike"] / max(0.01, float(spot))).replace([math.inf, -math.inf], 0).fillna(0)
    df["moneyness_pct"] = ((df["moneyness"] - 1.0) * 100).round(2)
    df["type"] = df["type"].fillna("").astype(str).str.lower()
    df["iv"] = df["iv"].where(df["iv"] <= 3, df["iv"] / 100)

    return df


def classify_surface_zone(row: pd.Series, policy: dict[str, Any] | None = None) -> str:
    policy = policy or DEFAULT_SURFACE_POLICY
    m = _num(row.get("moneyness_pct"), 0)
    opt_type = str(row.get("type", "")).lower()
    atm_band = float(policy.get("atm_moneyness_band_pct", 5.0))
    wing_band = float(policy.get("wing_moneyness_band_pct", 15.0))

    if abs(m) <= atm_band:
        return "ATM"
    if opt_type == "put" and m < -atm_band:
        return "PUT_WING" if abs(m) >= wing_band else "PUT_SKEW"
    if opt_type == "call" and m > atm_band:
        return "CALL_WING" if abs(m) >= wing_band else "CALL_SKEW"
    return "OTHER"


def build_volatility_surface(chain_data: Any, underlying_price: float | None = None, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = policy or DEFAULT_SURFACE_POLICY
    df = normalize_surface_chain(chain_data, underlying_price=underlying_price)

    if df.empty:
        return {"available": False, "reason": "No options chain rows available for volatility surface.", "surface": df}

    df = df[
        (df["volume"] >= float(policy.get("min_volume", 0)))
        & (df["open_interest"] >= float(policy.get("min_open_interest", 0)))
    ].copy()

    if df.empty:
        return {"available": False, "reason": "No options rows passed surface liquidity filters.", "surface": df}

    df["surface_zone"] = df.apply(lambda row: classify_surface_zone(row, policy), axis=1)

    surface_grid = (
        df.groupby(["expiry", "dte", "strike", "moneyness_pct", "type"], as_index=False)
        .agg(
            iv=("iv", "mean"),
            mid=("mid", "mean"),
            volume=("volume", "sum"),
            open_interest=("open_interest", "sum"),
            delta=("delta", "mean"),
            gamma=("gamma", "mean"),
            theta=("theta", "mean"),
            vega=("vega", "mean"),
        )
        .sort_values(["dte", "strike", "type"])
        .reset_index(drop=True)
    )

    expiry_summary = (
        df.groupby(["expiry", "dte"], as_index=False)
        .agg(
            avg_iv=("iv", "mean"),
            contracts=("iv", "size"),
            total_volume=("volume", "sum"),
            total_open_interest=("open_interest", "sum"),
        )
        .sort_values("dte")
        .reset_index(drop=True)
    )

    return {
        "available": True,
        "surface": df,
        "surface_grid": surface_grid,
        "expiry_summary": expiry_summary,
        "underlying_price": float(df["surface_underlying_price"].iloc[0]),
        "policy": policy,
    }


def analyze_skew(surface_report: dict[str, Any], policy: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = policy or DEFAULT_SURFACE_POLICY

    if not surface_report.get("available"):
        return surface_report

    df = surface_report.get("surface")
    if not isinstance(df, pd.DataFrame) or df.empty:
        return {"available": False, "reason": "No surface data available for skew."}

    rows = []
    for expiry, grp in df.groupby("expiry"):
        atm = grp[grp["surface_zone"] == "ATM"]["iv"].mean()
        put_wing = grp[grp["surface_zone"].isin(["PUT_SKEW", "PUT_WING"])]["iv"].mean()
        call_wing = grp[grp["surface_zone"].isin(["CALL_SKEW", "CALL_WING"])]["iv"].mean()

        atm = 0 if pd.isna(atm) else float(atm)
        put_wing = 0 if pd.isna(put_wing) else float(put_wing)
        call_wing = 0 if pd.isna(call_wing) else float(call_wing)

        put_skew = put_wing - atm
        call_skew = call_wing - atm
        skew_slope = put_wing - call_wing

        if skew_slope >= policy["steep_skew_threshold"]:
            regime = "PUT_SKEW_STEEP"
        elif call_skew >= policy["steep_skew_threshold"]:
            regime = "CALL_SKEW_STEEP"
        elif abs(skew_slope) <= 0.03:
            regime = "FLAT"
        else:
            regime = "NORMAL"

        rows.append({
            "expiry": expiry,
            "dte": float(grp["dte"].median()),
            "atm_iv": round(atm, 4),
            "put_wing_iv": round(put_wing, 4),
            "call_wing_iv": round(call_wing, 4),
            "put_skew": round(put_skew, 4),
            "call_skew": round(call_skew, 4),
            "skew_slope": round(skew_slope, 4),
            "skew_regime": regime,
        })

    return {"available": True, "skew": pd.DataFrame(rows).sort_values("dte").reset_index(drop=True)}


def analyze_term_structure(surface_report: dict[str, Any], policy: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = policy or DEFAULT_SURFACE_POLICY

    if not surface_report.get("available"):
        return surface_report

    term = surface_report.get("expiry_summary")
    if not isinstance(term, pd.DataFrame) or term.empty:
        return {"available": False, "reason": "No expiry summary available for term structure."}

    term = term.copy().sort_values("dte").reset_index(drop=True)
    term["iv_change"] = term["avg_iv"].diff().fillna(0)
    term["term_slope"] = term["avg_iv"] - float(term["avg_iv"].iloc[0])

    front_iv = float(term["avg_iv"].iloc[0])
    back_iv = float(term["avg_iv"].iloc[-1])
    slope = back_iv - front_iv

    if slope < -policy["term_inversion_threshold"]:
        regime = "BACKWARDATION"
    elif slope > policy["term_inversion_threshold"]:
        regime = "CONTANGO"
    else:
        regime = "FLAT"

    return {
        "available": True,
        "term_structure": term,
        "front_iv": round(front_iv, 4),
        "back_iv": round(back_iv, 4),
        "term_slope": round(slope, 4),
        "term_regime": regime,
    }


def classify_iv_regime(avg_iv: float, policy: dict[str, Any] | None = None) -> str:
    policy = policy or DEFAULT_SURFACE_POLICY
    if avg_iv >= policy["high_iv_threshold"]:
        return "HIGH_IV"
    if avg_iv <= policy["low_iv_threshold"]:
        return "LOW_IV"
    return "NORMAL_IV"


def find_surface_opportunities(surface_report: dict[str, Any], skew_report: dict[str, Any], term_report: dict[str, Any], policy: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = policy or DEFAULT_SURFACE_POLICY

    if not surface_report.get("available"):
        return surface_report

    df = surface_report.get("surface")
    if not isinstance(df, pd.DataFrame) or df.empty:
        return {"available": False, "reason": "No surface data available for opportunity scan."}

    avg_iv = float(df["iv"].mean())
    iv_regime = classify_iv_regime(avg_iv, policy)
    term_regime = term_report.get("term_regime", "UNKNOWN") if term_report.get("available") else "UNKNOWN"

    rows = []

    if iv_regime == "HIGH_IV":
        rows.append({
            "Opportunity": "Premium Selling Bias",
            "Regime": iv_regime,
            "Priority": "High",
            "Rationale": "Average implied volatility is elevated.",
            "Candidate Structures": "Credit spreads, iron condors, covered calls, cash-secured puts",
        })

    if iv_regime == "LOW_IV":
        rows.append({
            "Opportunity": "Long Volatility Bias",
            "Regime": iv_regime,
            "Priority": "Medium",
            "Rationale": "Average implied volatility is low.",
            "Candidate Structures": "Debit spreads, calendars, long straddles/strangles",
        })

    if term_regime == "BACKWARDATION":
        rows.append({
            "Opportunity": "Front Vol Richness",
            "Regime": term_regime,
            "Priority": "High",
            "Rationale": "Front-month IV is rich versus back-month IV.",
            "Candidate Structures": "Calendar spreads, diagonal spreads, front premium harvest",
        })
    elif term_regime == "CONTANGO":
        rows.append({
            "Opportunity": "Back Vol Premium",
            "Regime": term_regime,
            "Priority": "Normal",
            "Rationale": "Longer-dated IV is above front IV.",
            "Candidate Structures": "Longer-dated hedges, diagonal structures",
        })

    skew = skew_report.get("skew") if skew_report.get("available") else pd.DataFrame()
    if isinstance(skew, pd.DataFrame) and not skew.empty:
        steep = skew[skew["skew_regime"].isin(["PUT_SKEW_STEEP", "CALL_SKEW_STEEP"])]
        if not steep.empty:
            rows.append({
                "Opportunity": "Skew Structure",
                "Regime": ", ".join(sorted(steep["skew_regime"].unique())),
                "Priority": "High",
                "Rationale": "Surface skew is materially steep in at least one expiry.",
                "Candidate Structures": "Risk reversals, put spreads, call spreads, collars",
            })

    return {
        "available": True,
        "opportunities": pd.DataFrame(rows),
        "iv_regime": iv_regime,
        "avg_iv": round(avg_iv, 4),
    }


def build_volatility_surface_report(chain_data: Any, underlying_price: float | None = None, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = policy or DEFAULT_SURFACE_POLICY

    surface = build_volatility_surface(chain_data, underlying_price=underlying_price, policy=policy)
    if not surface.get("available"):
        return surface

    skew = analyze_skew(surface, policy=policy)
    term = analyze_term_structure(surface, policy=policy)
    opportunities = find_surface_opportunities(surface, skew, term, policy=policy)

    surface_df = surface.get("surface", pd.DataFrame())
    summary = {
        "underlying_price": surface.get("underlying_price", 0),
        "contract_count": int(len(surface_df)),
        "expiry_count": int(surface_df["expiry"].nunique()) if "expiry" in surface_df.columns else 0,
        "avg_iv": opportunities.get("avg_iv", 0),
        "iv_regime": opportunities.get("iv_regime", "UNKNOWN"),
        "term_regime": term.get("term_regime", "UNKNOWN") if term.get("available") else "UNKNOWN",
        "term_slope": term.get("term_slope", 0) if term.get("available") else 0,
        "opportunity_count": int(len(opportunities.get("opportunities", pd.DataFrame()))) if opportunities.get("available") else 0,
    }

    return {
        "available": True,
        "summary": summary,
        "surface": surface.get("surface"),
        "surface_grid": surface.get("surface_grid"),
        "expiry_summary": surface.get("expiry_summary"),
        "skew": skew,
        "term": term,
        "opportunities": opportunities,
        "policy": policy,
    }


def summarize_volatility_surface(report: dict[str, Any]) -> str:
    if not report.get("available"):
        return f"Volatility Surface unavailable: {report.get('reason', 'unknown reason')}"

    s = report.get("summary", {})
    return (
        f"Volatility Surface Intelligence analyzed {s.get('contract_count')} contracts "
        f"across {s.get('expiry_count')} expirations. "
        f"Average IV is {s.get('avg_iv')} with regime {s.get('iv_regime')}. "
        f"Term structure is {s.get('term_regime')} with slope {s.get('term_slope')}. "
        f"{s.get('opportunity_count')} surface opportunities were identified."
    )
