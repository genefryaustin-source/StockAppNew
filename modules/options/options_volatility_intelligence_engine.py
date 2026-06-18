"""
Sprint 4 Phase 4 — Volatility Intelligence Engine.

Professional volatility analytics layer for StockApp options:
- ATM IV
- IV rank proxy
- IV percentile proxy
- Term structure
- Skew analysis
- Expected move
- Volatility regime
- Volatility opportunity scanner

This module is deterministic and works from the normalized options chain payload
returned by modules.options.options_data_service.get_options_chain().
"""
from __future__ import annotations

from typing import Any

import math
import pandas as pd


def _as_frame(chain_data: dict[str, Any] | None) -> pd.DataFrame:
    if not chain_data:
        return pd.DataFrame()
    df = chain_data.get("all_rows")
    if isinstance(df, pd.DataFrame):
        return df.copy()
    if isinstance(df, list):
        return pd.DataFrame(df)
    return pd.DataFrame()


def _num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None:
            return default
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except Exception:
        return default


def _get_underlying_price(chain_data: dict[str, Any] | None, df: pd.DataFrame | None = None) -> float | None:
    if chain_data:
        for key in ("underlying_price", "price", "spot", "last_price", "current_price"):
            val = _safe_float(chain_data.get(key))
            if val and val > 0:
                return val

    if df is not None and not df.empty and "strike" in df.columns:
        strikes = _num(df["strike"]).dropna()
        if not strikes.empty:
            return float(strikes.median())

    return None


def _prepare(chain_data: dict[str, Any] | None, expiry: str | None = None) -> pd.DataFrame:
    df = _as_frame(chain_data)
    if df.empty:
        return df

    df = df.copy()

    for col in ["strike", "iv", "volume", "open_interest", "bid", "ask", "last", "delta", "dte"]:
        if col not in df.columns:
            df[col] = None

    if "type" not in df.columns:
        df["type"] = ""

    df["type"] = df["type"].astype(str).str.lower()
    df["strike"] = _num(df["strike"])
    df["iv"] = _num(df["iv"])
    df["volume"] = _num(df["volume"]).fillna(0)
    df["open_interest"] = _num(df["open_interest"]).fillna(0)
    df["bid"] = _num(df["bid"]).fillna(0)
    df["ask"] = _num(df["ask"]).fillna(0)
    df["last"] = _num(df["last"]).fillna(0)
    df["delta"] = _num(df["delta"])
    df["dte"] = _num(df["dte"])

    if expiry and "expiry" in df.columns:
        df = df[df["expiry"].astype(str) == str(expiry)]

    return df.dropna(subset=["strike"])


def calculate_atm_iv(chain_data: dict[str, Any] | None, expiry: str | None = None) -> dict[str, Any]:
    df = _prepare(chain_data, expiry)
    if df.empty:
        return {"available": False, "reason": "No chain rows available."}

    spot = _get_underlying_price(chain_data, df)
    if not spot:
        return {"available": False, "reason": "Unable to infer underlying price."}

    valid = df.dropna(subset=["iv"]).copy()
    valid = valid[valid["iv"] > 0]
    if valid.empty:
        return {"available": False, "reason": "No valid IV observations."}

    valid["distance"] = (valid["strike"] - spot).abs()
    atm = valid.sort_values(["distance", "volume", "open_interest"], ascending=[True, False, False]).head(8)

    atm_iv = float(atm["iv"].median())
    atm_strike = float(atm.iloc[0]["strike"])

    return {
        "available": True,
        "expiry": expiry,
        "underlying_price": spot,
        "atm_strike": atm_strike,
        "atm_iv": atm_iv,
        "atm_iv_pct": round(atm_iv * 100, 2),
        "sample_size": int(len(atm)),
    }


def calculate_term_structure(chain_data: dict[str, Any] | None) -> dict[str, Any]:
    df = _prepare(chain_data)
    if df.empty or "expiry" not in df.columns:
        return {"available": False, "reason": "No expiration data available."}

    valid = df.dropna(subset=["iv", "dte"]).copy()
    valid = valid[(valid["iv"] > 0) & (valid["dte"] >= 0)]
    if valid.empty:
        return {"available": False, "reason": "No valid IV/DTE observations."}

    term = (
        valid.groupby(["expiry", "dte"], as_index=False)
        .agg(
            avg_iv=("iv", "median"),
            volume=("volume", "sum"),
            open_interest=("open_interest", "sum"),
            contracts=("iv", "size"),
        )
        .sort_values("dte")
        .reset_index(drop=True)
    )

    if len(term) >= 2:
        front_iv = float(term.iloc[0]["avg_iv"])
        back_iv = float(term.iloc[-1]["avg_iv"])
        slope = back_iv - front_iv
    else:
        front_iv = float(term.iloc[0]["avg_iv"])
        back_iv = front_iv
        slope = 0.0

    if slope > 0.025:
        regime = "CONTANGO"
    elif slope < -0.025:
        regime = "BACKWARDATION"
    else:
        regime = "FLAT"

    term["avg_iv_pct"] = (term["avg_iv"] * 100).round(2)

    return {
        "available": True,
        "term_structure": term,
        "front_iv": round(front_iv * 100, 2),
        "back_iv": round(back_iv * 100, 2),
        "term_slope": round(slope * 100, 2),
        "term_regime": regime,
    }


def calculate_skew(chain_data: dict[str, Any] | None, expiry: str | None = None) -> dict[str, Any]:
    df = _prepare(chain_data, expiry)
    if df.empty:
        return {"available": False, "reason": "No chain rows available."}

    valid = df.dropna(subset=["iv"]).copy()
    valid = valid[valid["iv"] > 0]
    if valid.empty:
        return {"available": False, "reason": "No valid IV observations."}

    calls = valid[valid["type"] == "call"].copy()
    puts = valid[valid["type"] == "put"].copy()

    call_iv = float(calls["iv"].median()) if not calls.empty else None
    put_iv = float(puts["iv"].median()) if not puts.empty else None
    atm = calculate_atm_iv(chain_data, expiry)
    atm_iv = atm.get("atm_iv") if atm.get("available") else None

    skew = None
    if call_iv is not None and put_iv is not None:
        skew = (put_iv - call_iv) * 100

    if skew is None:
        regime = "UNKNOWN"
    elif skew >= 5:
        regime = "FEAR_SKEW"
    elif skew <= -3:
        regime = "CALL_DEMAND_SKEW"
    else:
        regime = "NEUTRAL_SKEW"

    return {
        "available": True,
        "expiry": expiry,
        "call_iv_pct": round(call_iv * 100, 2) if call_iv is not None else None,
        "put_iv_pct": round(put_iv * 100, 2) if put_iv is not None else None,
        "atm_iv_pct": round(atm_iv * 100, 2) if atm_iv is not None else None,
        "put_call_skew": round(skew, 2) if skew is not None else None,
        "skew_regime": regime,
    }


def calculate_expected_move(
    chain_data: dict[str, Any] | None,
    expiry: str | None = None,
    underlying_price: float | None = None,
) -> dict[str, Any]:
    df = _prepare(chain_data, expiry)
    if df.empty:
        return {"available": False, "reason": "No chain rows available."}

    spot = underlying_price or _get_underlying_price(chain_data, df)
    if not spot:
        return {"available": False, "reason": "Unable to infer underlying price."}

    atm = calculate_atm_iv(chain_data, expiry)
    if not atm.get("available"):
        return {"available": False, "reason": atm.get("reason", "ATM IV unavailable.")}

    dte = None
    if "dte" in df.columns:
        dtes = df["dte"].dropna()
        if not dtes.empty:
            dte = float(dtes.median())

    if dte is None or dte <= 0:
        return {"available": False, "reason": "DTE unavailable."}

    iv = float(atm["atm_iv"])
    expected_move = float(spot) * iv * math.sqrt(dte / 365)
    expected_move_pct = expected_move / float(spot) * 100

    return {
        "available": True,
        "expiry": expiry,
        "underlying_price": round(float(spot), 2),
        "dte": int(round(dte)),
        "atm_iv_pct": round(iv * 100, 2),
        "expected_move": round(expected_move, 2),
        "expected_move_pct": round(expected_move_pct, 2),
        "upper_range": round(float(spot) + expected_move, 2),
        "lower_range": round(float(spot) - expected_move, 2),
    }


def calculate_iv_rank_percentile_proxy(chain_data: dict[str, Any] | None) -> dict[str, Any]:
    """
    Proxy IV Rank/Percentile from current chain distribution when historical IV is unavailable.
    This is not a true 52-week historical IV Rank; it is a cross-chain proxy.
    """
    df = _prepare(chain_data)
    valid = df.dropna(subset=["iv"]).copy()
    valid = valid[valid["iv"] > 0]

    if valid.empty:
        return {"available": False, "reason": "No valid IV observations."}

    atm = calculate_atm_iv(chain_data)
    current_iv = atm.get("atm_iv") if atm.get("available") else float(valid["iv"].median())

    low = float(valid["iv"].quantile(0.05))
    high = float(valid["iv"].quantile(0.95))
    denom = max(0.0001, high - low)
    iv_rank = max(0.0, min(100.0, ((float(current_iv) - low) / denom) * 100))
    iv_percentile = float((valid["iv"] <= float(current_iv)).mean() * 100)

    return {
        "available": True,
        "current_iv_pct": round(float(current_iv) * 100, 2),
        "iv_low_proxy_pct": round(low * 100, 2),
        "iv_high_proxy_pct": round(high * 100, 2),
        "iv_rank_proxy": round(iv_rank, 2),
        "iv_percentile_proxy": round(iv_percentile, 2),
        "note": "Proxy uses current option-chain IV distribution, not 52-week historical IV.",
    }


def classify_volatility_regime(chain_data: dict[str, Any] | None, expiry: str | None = None) -> dict[str, Any]:
    atm = calculate_atm_iv(chain_data, expiry)
    rank = calculate_iv_rank_percentile_proxy(chain_data)
    skew = calculate_skew(chain_data, expiry)
    term = calculate_term_structure(chain_data)
    em = calculate_expected_move(chain_data, expiry)

    if not atm.get("available"):
        return {
            "available": False,
            "reason": atm.get("reason", "ATM IV unavailable."),
            "atm": atm,
            "rank": rank,
            "skew": skew,
            "term": term,
            "expected_move": em,
        }

    iv = float(atm.get("atm_iv_pct", 0))
    iv_rank = rank.get("iv_rank_proxy", 50) if rank.get("available") else 50

    if iv_rank >= 85 or iv >= 90:
        regime = "EXTREME_VOL"
        strategy_bias = "SHORT_PREMIUM_OR_DEFINED_RISK"
    elif iv_rank >= 65 or iv >= 60:
        regime = "ELEVATED_VOL"
        strategy_bias = "CREDIT_SPREADS_CONDORS_CALENDARS"
    elif iv_rank <= 20 or iv <= 20:
        regime = "LOW_VOL"
        strategy_bias = "LONG_PREMIUM_OR_DEBIT_SPREADS"
    else:
        regime = "NORMAL_VOL"
        strategy_bias = "BALANCED_STRATEGIES"

    if term.get("available") and term.get("term_regime") == "BACKWARDATION":
        regime = "EVENT_VOL" if regime != "EXTREME_VOL" else regime

    return {
        "available": True,
        "expiry": expiry,
        "volatility_regime": regime,
        "strategy_bias": strategy_bias,
        "atm": atm,
        "rank": rank,
        "skew": skew,
        "term": term,
        "expected_move": em,
    }


def scan_volatility_opportunities(chain_data: dict[str, Any] | None, expiry: str | None = None) -> dict[str, Any]:
    regime = classify_volatility_regime(chain_data, expiry)
    if not regime.get("available"):
        return {"available": False, "reason": regime.get("reason", "Volatility regime unavailable.")}

    vol_regime = regime.get("volatility_regime")
    skew_regime = regime.get("skew", {}).get("skew_regime")
    term_regime = regime.get("term", {}).get("term_regime")

    opportunities: list[dict[str, Any]] = []

    if vol_regime in {"ELEVATED_VOL", "EXTREME_VOL", "EVENT_VOL"}:
        opportunities.extend([
            {"strategy": "Iron Condor", "direction": "Neutral", "rationale": "Elevated IV supports defined-risk premium selling."},
            {"strategy": "Credit Spread", "direction": "Directional", "rationale": "High IV allows selling rich premium with capped risk."},
        ])

    if vol_regime in {"LOW_VOL", "NORMAL_VOL"}:
        opportunities.extend([
            {"strategy": "Debit Spread", "direction": "Directional", "rationale": "Lower IV favors defined-risk long premium exposure."},
            {"strategy": "Long Calendar", "direction": "Neutral", "rationale": "Can benefit from term-structure normalization."},
        ])

    if skew_regime == "FEAR_SKEW":
        opportunities.append({"strategy": "Put Credit Spread", "direction": "Bullish/Neutral", "rationale": "Put skew is rich; defined-risk put premium may be attractive."})

    if skew_regime == "CALL_DEMAND_SKEW":
        opportunities.append({"strategy": "Call Credit Spread", "direction": "Bearish/Neutral", "rationale": "Call skew is rich; upside premium may be overpriced."})

    if term_regime == "BACKWARDATION":
        opportunities.append({"strategy": "Post-Event Vol Crush", "direction": "Event", "rationale": "Front IV is rich versus back IV; monitor for crush."})

    if not opportunities:
        opportunities.append({"strategy": "Watchlist", "direction": "Neutral", "rationale": "No clear volatility edge detected."})

    return {
        "available": True,
        "volatility_regime": vol_regime,
        "opportunities": opportunities,
    }


def build_volatility_intelligence_report(chain_data: dict[str, Any] | None, expiry: str | None = None) -> dict[str, Any]:
    regime = classify_volatility_regime(chain_data, expiry)
    opportunities = scan_volatility_opportunities(chain_data, expiry)

    if not regime.get("available"):
        return {
            "available": False,
            "reason": regime.get("reason", "Volatility intelligence unavailable."),
            "regime": regime,
            "opportunities": opportunities,
        }

    return {
        "available": True,
        "expiry": expiry,
        "volatility_regime": regime.get("volatility_regime"),
        "strategy_bias": regime.get("strategy_bias"),
        "atm": regime.get("atm", {}),
        "rank": regime.get("rank", {}),
        "skew": regime.get("skew", {}),
        "term": regime.get("term", {}),
        "expected_move": regime.get("expected_move", {}),
        "opportunities": opportunities.get("opportunities", []),
    }


def summarize_volatility_intelligence(report: dict[str, Any]) -> str:
    if not report.get("available"):
        return f"Volatility intelligence unavailable: {report.get('reason', 'unknown reason')}"
    em = report.get("expected_move", {})
    em_text = ""
    if em.get("available"):
        em_text = f" Expected move: ±${em.get('expected_move')} ({em.get('expected_move_pct')}%)."
    return (
        f"Volatility regime: {report.get('volatility_regime')} | "
        f"Strategy bias: {report.get('strategy_bias')}."
        f"{em_text}"
    )
