"""
Sprint 10 Phase 2 — Volatility Regime Intelligence Engine.

Institutional volatility regime analytics:
- IV regime classification
- IV rank / IV percentile
- Realized-vol proxy
- Implied vs realized volatility spread
- Volatility risk premium
- Regime transition detection
- Regime persistence / stability score
- Trade recommendation framework

This module does not place trades. It creates deterministic volatility-regime
diagnostics for dashboards and future volatility command-center modules.
"""
from __future__ import annotations

from typing import Any
import math
import pandas as pd


DEFAULT_VOL_REGIME_POLICY = {
    "extreme_low_iv": 0.12,
    "low_iv": 0.20,
    "elevated_iv": 0.45,
    "high_iv": 0.65,
    "crisis_iv": 0.90,
    "iv_rank_low": 20.0,
    "iv_rank_high": 70.0,
    "vrp_positive_threshold": 0.05,
    "vrp_negative_threshold": -0.05,
    "min_volume": 0,
    "min_open_interest": 0,
}


def _df(data: Any) -> pd.DataFrame:
    if isinstance(data, pd.DataFrame):
        return data.copy()
    if isinstance(data, list):
        return pd.DataFrame(data)
    if isinstance(data, dict):
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


def normalize_regime_chain(chain_data: Any) -> pd.DataFrame:
    df = _extract_chain_rows(chain_data)

    if df.empty:
        return df

    df = df.copy()

    defaults = {
        "expiry": "",
        "type": "",
        "strike": 0,
        "iv": 0,
        "mid": 0,
        "bid": 0,
        "ask": 0,
        "last": 0,
        "volume": 0,
        "open_interest": 0,
        "dte": 30,
        "delta": 0,
        "gamma": 0,
        "theta": 0,
        "vega": 0,
        "underlying_price": 0,
        "spot": 0,
        "last_underlying_price": 0,
    }

    for col, default in defaults.items():
        if col not in df.columns:
            df[col] = default

    numeric_cols = [
        "strike", "iv", "mid", "bid", "ask", "last", "volume", "open_interest",
        "dte", "delta", "gamma", "theta", "vega",
        "underlying_price", "spot", "last_underlying_price",
    ]

    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["iv"] = df["iv"].where(df["iv"] <= 3, df["iv"] / 100)
    df["mid"] = df["mid"].where(df["mid"] > 0, ((df["bid"] + df["ask"]) / 2))
    df["mid"] = df["mid"].where(df["mid"] > 0, df["last"])
    df["type"] = df["type"].fillna("").astype(str).str.lower()

    return df


def classify_volatility_regime(avg_iv: float, policy: dict[str, Any] | None = None) -> str:
    policy = policy or DEFAULT_VOL_REGIME_POLICY

    if avg_iv >= policy["crisis_iv"]:
        return "CRISIS_VOL"
    if avg_iv >= policy["high_iv"]:
        return "HIGH_VOL"
    if avg_iv >= policy["elevated_iv"]:
        return "ELEVATED_VOL"
    if avg_iv <= policy["extreme_low_iv"]:
        return "EXTREME_LOW_VOL"
    if avg_iv <= policy["low_iv"]:
        return "LOW_VOL"
    return "NORMAL_VOL"


def calculate_iv_rank(avg_iv: float, iv_min: float, iv_max: float) -> float:
    if iv_max <= iv_min:
        return 50.0
    return round(max(0.0, min(100.0, (avg_iv - iv_min) / (iv_max - iv_min) * 100)), 2)


def calculate_iv_percentile(avg_iv: float, iv_series: pd.Series) -> float:
    series = pd.to_numeric(iv_series, errors="coerce").dropna()
    if series.empty:
        return 50.0
    return round(float((series <= avg_iv).mean() * 100), 2)


def estimate_realized_vol_proxy(df: pd.DataFrame) -> float:
    """
    Defensive realized-vol proxy when historical prices are not available.
    Uses cross-expiry ATM-ish IV and option dispersion to create a stable placeholder.
    """
    if df.empty or "iv" not in df.columns:
        return 0.0

    iv = pd.to_numeric(df["iv"], errors="coerce").dropna()
    if iv.empty:
        return 0.0

    avg_iv = float(iv.mean())
    iv_dispersion = float(iv.std()) if len(iv) > 1 else avg_iv * 0.20
    rv_proxy = max(0.01, avg_iv - min(avg_iv * 0.30, iv_dispersion * 0.50))
    return round(rv_proxy, 4)


def calculate_volatility_risk_premium(avg_iv: float, realized_vol: float) -> dict[str, Any]:
    spread = avg_iv - realized_vol

    if spread > DEFAULT_VOL_REGIME_POLICY["vrp_positive_threshold"]:
        regime = "POSITIVE_VRP"
        interpretation = "Implied volatility is rich versus realized-vol proxy."
    elif spread < DEFAULT_VOL_REGIME_POLICY["vrp_negative_threshold"]:
        regime = "NEGATIVE_VRP"
        interpretation = "Implied volatility is cheap versus realized-vol proxy."
    else:
        regime = "NEUTRAL_VRP"
        interpretation = "Implied and realized-vol proxy are broadly aligned."

    return {
        "realized_vol_proxy": round(realized_vol, 4),
        "iv_rv_spread": round(spread, 4),
        "volatility_risk_premium": regime,
        "vrp_interpretation": interpretation,
    }


def build_regime_by_expiry(df: pd.DataFrame, policy: dict[str, Any] | None = None) -> pd.DataFrame:
    policy = policy or DEFAULT_VOL_REGIME_POLICY

    if df.empty:
        return pd.DataFrame()

    table = (
        df.groupby(["expiry", "dte"], as_index=False)
        .agg(
            avg_iv=("iv", "mean"),
            min_iv=("iv", "min"),
            max_iv=("iv", "max"),
            contracts=("iv", "size"),
            total_volume=("volume", "sum"),
            total_open_interest=("open_interest", "sum"),
        )
        .sort_values("dte")
        .reset_index(drop=True)
    )

    table["iv_rank"] = table.apply(
        lambda row: calculate_iv_rank(row["avg_iv"], row["min_iv"], row["max_iv"]),
        axis=1,
    )
    table["iv_regime"] = table["avg_iv"].apply(lambda v: classify_volatility_regime(float(v), policy))

    for col in ["avg_iv", "min_iv", "max_iv"]:
        table[col] = pd.to_numeric(table[col], errors="coerce").fillna(0).round(4)

    return table


def detect_regime_transition(regime_by_expiry: pd.DataFrame) -> dict[str, Any]:
    if not isinstance(regime_by_expiry, pd.DataFrame) or regime_by_expiry.empty:
        return {
            "available": False,
            "transition": "UNKNOWN",
            "transition_score": 0,
            "reason": "No expiry regime data available.",
        }

    regimes = list(regime_by_expiry.sort_values("dte")["iv_regime"])
    if len(regimes) < 2:
        return {
            "available": True,
            "transition": "SINGLE_EXPIRY",
            "transition_score": 25,
            "reason": "Only one expiry available.",
        }

    front = regimes[0]
    back = regimes[-1]

    transition = f"{front}_TO_{back}"
    transition_score = 50

    if "LOW" in front and ("HIGH" in back or "ELEVATED" in back):
        transition_score = 70
        reason = "Back expiries price higher volatility than front expiry."
    elif ("HIGH" in front or "CRISIS" in front) and ("LOW" in back or "NORMAL" in back):
        transition_score = 80
        reason = "Front volatility is elevated versus calmer back expiries."
    elif front == back:
        transition_score = 35
        reason = "Volatility regime is consistent across expiries."
    else:
        reason = "Mixed term-regime transition detected."

    return {
        "available": True,
        "transition": transition,
        "front_regime": front,
        "back_regime": back,
        "transition_score": transition_score,
        "reason": reason,
    }


def estimate_regime_persistence(regime_by_expiry: pd.DataFrame, current_regime: str) -> dict[str, Any]:
    if not isinstance(regime_by_expiry, pd.DataFrame) or regime_by_expiry.empty:
        return {
            "available": False,
            "stability_score": 0,
            "dominant_regime": current_regime,
            "dominant_frequency_pct": 0,
        }

    counts = regime_by_expiry["iv_regime"].value_counts()
    dominant = str(counts.index[0])
    freq = float(counts.iloc[0] / max(1, len(regime_by_expiry)) * 100)

    dte_span = float(regime_by_expiry["dte"].max() - regime_by_expiry["dte"].min()) if "dte" in regime_by_expiry.columns else 0
    stability = min(100.0, freq * 0.75 + min(25, dte_span / 4))

    return {
        "available": True,
        "stability_score": round(stability, 2),
        "dominant_regime": dominant,
        "dominant_frequency_pct": round(freq, 2),
        "regime_consistent": dominant == current_regime,
    }


def build_trade_recommendations(
    regime: str,
    iv_rank: float,
    iv_percentile: float,
    vrp: dict[str, Any],
    transition: dict[str, Any],
) -> pd.DataFrame:
    rows = []
    vrp_state = vrp.get("volatility_risk_premium", "NEUTRAL_VRP")
    transition_name = transition.get("transition", "UNKNOWN")

    if regime in {"HIGH_VOL", "CRISIS_VOL", "ELEVATED_VOL"} and vrp_state == "POSITIVE_VRP":
        rows.append({
            "Recommendation": "Short Volatility Bias",
            "Priority": "High",
            "Rationale": "Implied volatility is elevated and rich versus realized-vol proxy.",
            "Candidate Structures": "Credit spreads, iron condors, covered calls, cash-secured puts",
        })

    if regime in {"LOW_VOL", "EXTREME_LOW_VOL"} or iv_rank <= 20 or iv_percentile <= 20:
        rows.append({
            "Recommendation": "Long Volatility Bias",
            "Priority": "Medium",
            "Rationale": "Volatility is low by regime/rank/percentile.",
            "Candidate Structures": "Debit spreads, calendars, long straddles/strangles",
        })

    if "CRISIS" in transition_name or "HIGH" in transition_name:
        rows.append({
            "Recommendation": "Volatility Transition Trade",
            "Priority": "High",
            "Rationale": "Term-regime transition indicates possible volatility repricing.",
            "Candidate Structures": "Calendars, diagonals, front/back vol spreads",
        })

    if vrp_state == "NEGATIVE_VRP":
        rows.append({
            "Recommendation": "Cheap Implied Vol Review",
            "Priority": "Medium",
            "Rationale": "Implied volatility is below realized-vol proxy.",
            "Candidate Structures": "Long gamma, debit spreads, event-vol trades",
        })

    if not rows:
        rows.append({
            "Recommendation": "Neutral Volatility Posture",
            "Priority": "Normal",
            "Rationale": "Volatility conditions are balanced.",
            "Candidate Structures": "Defined-risk spreads, balanced premium structures",
        })

    return pd.DataFrame(rows)


def build_volatility_regime_report(
    chain_data: Any,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or DEFAULT_VOL_REGIME_POLICY
    df = normalize_regime_chain(chain_data)

    if df.empty:
        return {
            "available": False,
            "reason": "No options chain rows available for volatility regime analysis.",
            "positions": df,
        }

    df = df[
        (df["volume"] >= float(policy.get("min_volume", 0)))
        & (df["open_interest"] >= float(policy.get("min_open_interest", 0)))
    ].copy()

    if df.empty:
        return {
            "available": False,
            "reason": "No options rows passed volatility regime liquidity filters.",
            "positions": df,
        }

    avg_iv = float(df["iv"].mean())
    min_iv = float(df["iv"].min())
    max_iv = float(df["iv"].max())
    regime = classify_volatility_regime(avg_iv, policy)
    iv_rank = calculate_iv_rank(avg_iv, min_iv, max_iv)
    iv_percentile = calculate_iv_percentile(avg_iv, df["iv"])
    realized_vol = estimate_realized_vol_proxy(df)
    vrp = calculate_volatility_risk_premium(avg_iv, realized_vol)

    by_expiry = build_regime_by_expiry(df, policy)
    transition = detect_regime_transition(by_expiry)
    persistence = estimate_regime_persistence(by_expiry, regime)
    recommendations = build_trade_recommendations(
        regime=regime,
        iv_rank=iv_rank,
        iv_percentile=iv_percentile,
        vrp=vrp,
        transition=transition,
    )

    summary = {
        "avg_iv": round(avg_iv, 4),
        "min_iv": round(min_iv, 4),
        "max_iv": round(max_iv, 4),
        "iv_rank": iv_rank,
        "iv_percentile": iv_percentile,
        "current_regime": regime,
        "realized_vol_proxy": vrp.get("realized_vol_proxy", 0),
        "iv_rv_spread": vrp.get("iv_rv_spread", 0),
        "volatility_risk_premium": vrp.get("volatility_risk_premium", "UNKNOWN"),
        "transition": transition.get("transition", "UNKNOWN"),
        "stability_score": persistence.get("stability_score", 0),
        "contract_count": int(len(df)),
        "expiry_count": int(df["expiry"].nunique()) if "expiry" in df.columns else 0,
    }

    return {
        "available": True,
        "summary": summary,
        "chain": df,
        "by_expiry": by_expiry,
        "transition": transition,
        "persistence": persistence,
        "vrp": vrp,
        "recommendations": recommendations,
        "policy": policy,
    }


def summarize_volatility_regime(report: dict[str, Any]) -> str:
    if not report.get("available"):
        return f"Volatility Regime unavailable: {report.get('reason', 'unknown reason')}"

    s = report.get("summary", {})
    return (
        f"Volatility Regime is {s.get('current_regime')} with average IV {s.get('avg_iv')}, "
        f"IV Rank {s.get('iv_rank')}, IV Percentile {s.get('iv_percentile')}, "
        f"and VRP state {s.get('volatility_risk_premium')}. "
        f"Transition signal is {s.get('transition')} with stability {s.get('stability_score')}/100."
    )
