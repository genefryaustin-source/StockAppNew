
"""
Sprint 10 Phase 4 — Skew Intelligence Engine
"""
from __future__ import annotations

from typing import Any
import pandas as pd

DEFAULT_SKEW_POLICY = {
    "atm_band_pct": 5.0,
    "wing_band_pct": 15.0,
    "steep_put_skew": 0.10,
    "steep_call_skew": 0.10,
    "risk_reversal_threshold": 0.08,
}


def _df(data: Any) -> pd.DataFrame:
    if isinstance(data, pd.DataFrame):
        return data.copy()
    if isinstance(data, list):
        return pd.DataFrame(data)
    return pd.DataFrame()


def normalize_skew_chain(chain_data):
    if isinstance(chain_data, dict):
        for key in ["surface", "all_rows", "data"]:
            if isinstance(chain_data.get(key), pd.DataFrame):
                df = chain_data[key].copy()
                break
        else:
            df = pd.DataFrame()
    else:
        df = _df(chain_data)

    if df.empty:
        return df

    for col in ["iv", "strike", "dte", "moneyness_pct"]:
        if col not in df.columns:
            df[col] = 0

    df["iv"] = pd.to_numeric(df["iv"], errors="coerce").fillna(0)
    df["moneyness_pct"] = pd.to_numeric(df["moneyness_pct"], errors="coerce").fillna(0)

    if "type" not in df.columns:
        df["type"] = ""

    df["type"] = df["type"].astype(str).str.lower()

    return df


def classify_skew_zone(row, policy=None):
    policy = policy or DEFAULT_SKEW_POLICY
    m = float(row.get("moneyness_pct", 0))
    opt_type = str(row.get("type", "")).lower()

    if abs(m) <= policy["atm_band_pct"]:
        return "ATM"

    if opt_type == "put" and m < 0:
        return "PUT_WING" if abs(m) >= policy["wing_band_pct"] else "PUT_SKEW"

    if opt_type == "call" and m > 0:
        return "CALL_WING" if abs(m) >= policy["wing_band_pct"] else "CALL_SKEW"

    return "OTHER"


def build_skew_curve(chain_data, policy=None):
    policy = policy or DEFAULT_SKEW_POLICY
    df = normalize_skew_chain(chain_data)

    if df.empty:
        return {"available": False, "reason": "No skew data available."}

    df["skew_zone"] = df.apply(lambda r: classify_skew_zone(r, policy), axis=1)

    rows = []

    expiries = ["ALL"]
    if "expiry" in df.columns:
        expiries += sorted(df["expiry"].dropna().astype(str).unique().tolist())

    for expiry in expiries:
        grp = df if expiry == "ALL" else df[df["expiry"].astype(str) == expiry]

        if grp.empty:
            continue

        atm_iv = grp[grp["skew_zone"] == "ATM"]["iv"].mean()
        put_iv = grp[grp["skew_zone"].isin(["PUT_SKEW", "PUT_WING"])]["iv"].mean()
        call_iv = grp[grp["skew_zone"].isin(["CALL_SKEW", "CALL_WING"])]["iv"].mean()

        atm_iv = 0 if pd.isna(atm_iv) else float(atm_iv)
        put_iv = 0 if pd.isna(put_iv) else float(put_iv)
        call_iv = 0 if pd.isna(call_iv) else float(call_iv)

        put_skew = put_iv - atm_iv
        call_skew = call_iv - atm_iv
        risk_reversal = call_iv - put_iv

        rows.append({
            "expiry": expiry,
            "atm_iv": round(atm_iv, 4),
            "put_iv": round(put_iv, 4),
            "call_iv": round(call_iv, 4),
            "put_skew": round(put_skew, 4),
            "call_skew": round(call_skew, 4),
            "risk_reversal": round(risk_reversal, 4),
        })

    return {
        "available": True,
        "skew_curve": pd.DataFrame(rows)
    }


def classify_skew_regime(skew_curve, policy=None):
    policy = policy or DEFAULT_SKEW_POLICY

    if not isinstance(skew_curve, pd.DataFrame) or skew_curve.empty:
        return {
            "available": False,
            "regime": "UNKNOWN",
        }

    base = skew_curve.iloc[0]

    put_skew = float(base["put_skew"])
    call_skew = float(base["call_skew"])
    rr = float(base["risk_reversal"])

    if put_skew >= policy["steep_put_skew"]:
        regime = "PUT_SKEW_STEEP"
    elif call_skew >= policy["steep_call_skew"]:
        regime = "CALL_SKEW_STEEP"
    elif abs(rr) <= 0.03:
        regime = "BALANCED"
    else:
        regime = "NORMAL"

    return {
        "available": True,
        "regime": regime,
        "put_skew": round(put_skew, 4),
        "call_skew": round(call_skew, 4),
        "risk_reversal": round(rr, 4),
    }


def build_skew_opportunities(skew_state, policy=None):
    policy = policy or DEFAULT_SKEW_POLICY

    regime = skew_state.get("regime", "UNKNOWN")
    rr = float(skew_state.get("risk_reversal", 0))

    rows = []

    if regime == "PUT_SKEW_STEEP":
        rows.append({
            "Opportunity": "Put Skew Premium",
            "Priority": "High",
            "Structure": "Put spreads, collars, put credit spreads",
            "Rationale": "Downside protection is richly priced."
        })

    if regime == "CALL_SKEW_STEEP":
        rows.append({
            "Opportunity": "Call Skew Premium",
            "Priority": "High",
            "Structure": "Call spreads, covered calls",
            "Rationale": "Upside volatility is richly priced."
        })

    if rr <= -policy["risk_reversal_threshold"]:
        rows.append({
            "Opportunity": "Bullish Risk Reversal",
            "Priority": "Medium",
            "Structure": "Long call / short put",
            "Rationale": "Put skew dominates call skew."
        })

    elif rr >= policy["risk_reversal_threshold"]:
        rows.append({
            "Opportunity": "Bearish Risk Reversal",
            "Priority": "Medium",
            "Structure": "Long put / short call",
            "Rationale": "Call skew dominates put skew."
        })

    if not rows:
        rows.append({
            "Opportunity": "Neutral Skew",
            "Priority": "Normal",
            "Structure": "Balanced spreads",
            "Rationale": "Skew conditions are normal."
        })

    return pd.DataFrame(rows)


def build_skew_intelligence_report(chain_data, policy=None):
    policy = policy or DEFAULT_SKEW_POLICY

    curve = build_skew_curve(chain_data, policy)

    if not curve.get("available"):
        return curve

    skew_curve = curve["skew_curve"]

    state = classify_skew_regime(skew_curve, policy)
    opportunities = build_skew_opportunities(state, policy)

    summary = {
        "regime": state.get("regime"),
        "put_skew": state.get("put_skew"),
        "call_skew": state.get("call_skew"),
        "risk_reversal": state.get("risk_reversal"),
        "opportunity_count": len(opportunities),
    }

    return {
        "available": True,
        "summary": summary,
        "skew_curve": skew_curve,
        "state": state,
        "opportunities": opportunities,
    }


def summarize_skew_intelligence(report):
    if not report.get("available"):
        return report.get("reason", "No skew intelligence available.")

    s = report["summary"]

    return (
        f"Skew regime is {s['regime']}. "
        f"Put skew={s['put_skew']}, "
        f"Call skew={s['call_skew']}, "
        f"Risk Reversal={s['risk_reversal']}. "
        f"{s['opportunity_count']} skew opportunities detected."
    )
