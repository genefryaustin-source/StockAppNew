"""
Sprint 11 Phase 1 — Dealer Positioning Intelligence Engine.

Institutional market-making analytics:
- Dealer gamma exposure proxy
- Dealer delta exposure proxy
- Dealer vega exposure proxy
- Call wall / put wall detection
- Gamma flip estimate
- Dealer hedging pressure classification
- Positioning regime and action intelligence

This module does not place trades. It creates deterministic dealer-positioning
diagnostics from options-chain data.
"""
from __future__ import annotations

from typing import Any
import math
import pandas as pd


DEFAULT_DEALER_POSITIONING_POLICY = {
    "contract_multiplier": 100,
    "gamma_pressure_threshold": 1_000_000,
    "delta_pressure_threshold": 1_000_000,
    "vega_pressure_threshold": 500_000,
    "wall_oi_quantile": 0.90,
    "near_money_band_pct": 5.0,
    "min_open_interest": 0,
    "min_volume": 0,
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

def calculate_dealer_positioning(
    chain_data,
    underlying_price=None,
    *args,
    **kwargs,
):
    """
    Backward compatibility wrapper.

    Legacy dashboards still import:

        calculate_dealer_positioning()

    Sprint 11 renamed the implementation to:

        build_dealer_positioning_report()
    """

    return build_dealer_positioning_report(
        chain_data=chain_data,
        underlying_price=underlying_price,
    )

def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def normalize_dealer_chain(chain_data: Any, underlying_price: float | None = None) -> pd.DataFrame:
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

    df["type"] = df["type"].fillna("").astype(str).str.lower()
    df["iv"] = df["iv"].where(df["iv"] <= 3, df["iv"] / 100)
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

    df["dealer_underlying_price"] = float(spot)
    df["moneyness_pct"] = ((df["strike"] / max(0.01, float(spot))) - 1.0) * 100

    return df


def calculate_dealer_exposures(
    chain_data: Any,
    underlying_price: float | None = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or DEFAULT_DEALER_POSITIONING_POLICY
    df = normalize_dealer_chain(chain_data, underlying_price=underlying_price)

    if df.empty:
        return {
            "available": False,
            "reason": "No options chain data available for dealer positioning.",
            "chain": df,
        }

    df = df[
        (df["open_interest"] >= float(policy.get("min_open_interest", 0)))
        & (df["volume"] >= float(policy.get("min_volume", 0)))
    ].copy()

    if df.empty:
        return {
            "available": False,
            "reason": "No options rows passed dealer positioning liquidity filters.",
            "chain": df,
        }

    multiplier = float(policy.get("contract_multiplier", 100))
    spot = float(df["dealer_underlying_price"].iloc[0])

    # Dealer proxy convention:
    # public long calls -> dealer short call gamma/delta
    # public long puts -> dealer short put gamma, delta sign adjusted.
    direction = df["type"].map({"call": -1.0, "put": -1.0}).fillna(-1.0)

    df["dealer_gamma_exposure"] = direction * df["gamma"] * df["open_interest"] * multiplier * (spot ** 2) * 0.01
    df["dealer_delta_exposure"] = direction * df["delta"] * df["open_interest"] * multiplier * spot
    df["dealer_vega_exposure"] = direction * df["vega"] * df["open_interest"] * multiplier

    # For puts, user-facing delta is often negative. Dealer short put exposure can create positive hedge pressure.
    put_mask = df["type"].eq("put")
    df.loc[put_mask, "dealer_delta_exposure"] = -1.0 * df.loc[put_mask, "delta"] * df.loc[put_mask, "open_interest"] * multiplier * spot

    total_gamma = float(df["dealer_gamma_exposure"].sum())
    total_delta = float(df["dealer_delta_exposure"].sum())
    total_vega = float(df["dealer_vega_exposure"].sum())

    by_strike = (
        df.groupby("strike", as_index=False)
        .agg(
            dealer_gamma_exposure=("dealer_gamma_exposure", "sum"),
            dealer_delta_exposure=("dealer_delta_exposure", "sum"),
            dealer_vega_exposure=("dealer_vega_exposure", "sum"),
            open_interest=("open_interest", "sum"),
            volume=("volume", "sum"),
            avg_iv=("iv", "mean"),
        )
        .sort_values("strike")
        .reset_index(drop=True)
    )

    by_expiry = (
        df.groupby(["expiry", "dte"], as_index=False)
        .agg(
            dealer_gamma_exposure=("dealer_gamma_exposure", "sum"),
            dealer_delta_exposure=("dealer_delta_exposure", "sum"),
            dealer_vega_exposure=("dealer_vega_exposure", "sum"),
            open_interest=("open_interest", "sum"),
            volume=("volume", "sum"),
            avg_iv=("iv", "mean"),
        )
        .sort_values("dte")
        .reset_index(drop=True)
    )

    return {
        "available": True,
        "chain": df,
        "by_strike": by_strike,
        "by_expiry": by_expiry,
        "summary": {
            "underlying_price": round(spot, 4),
            "total_dealer_gamma": round(total_gamma, 2),
            "total_dealer_delta": round(total_delta, 2),
            "total_dealer_vega": round(total_vega, 2),
            "contract_count": int(len(df)),
            "expiry_count": int(df["expiry"].nunique()) if "expiry" in df.columns else 0,
            "strike_count": int(df["strike"].nunique()) if "strike" in df.columns else 0,
        },
        "policy": policy,
    }


def detect_dealer_walls(exposure_report: dict[str, Any], policy: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = policy or DEFAULT_DEALER_POSITIONING_POLICY

    if not exposure_report.get("available"):
        return exposure_report

    df = exposure_report.get("chain")
    if not isinstance(df, pd.DataFrame) or df.empty:
        return {"available": False, "reason": "No dealer chain available for wall detection."}

    oi_threshold = float(df["open_interest"].quantile(float(policy.get("wall_oi_quantile", 0.90))))
    walls = df[df["open_interest"] >= oi_threshold].copy()

    call_walls = walls[walls["type"].eq("call")].sort_values("open_interest", ascending=False).head(10)
    put_walls = walls[walls["type"].eq("put")].sort_values("open_interest", ascending=False).head(10)

    top_call_wall = float(call_walls["strike"].iloc[0]) if not call_walls.empty else 0
    top_put_wall = float(put_walls["strike"].iloc[0]) if not put_walls.empty else 0

    return {
        "available": True,
        "walls": walls.sort_values("open_interest", ascending=False).reset_index(drop=True),
        "call_walls": call_walls.reset_index(drop=True),
        "put_walls": put_walls.reset_index(drop=True),
        "summary": {
            "oi_threshold": round(oi_threshold, 2),
            "top_call_wall": round(top_call_wall, 2),
            "top_put_wall": round(top_put_wall, 2),
            "wall_count": int(len(walls)),
        },
    }


def estimate_gamma_flip(exposure_report: dict[str, Any]) -> dict[str, Any]:
    if not exposure_report.get("available"):
        return exposure_report

    by_strike = exposure_report.get("by_strike")
    if not isinstance(by_strike, pd.DataFrame) or by_strike.empty:
        return {"available": False, "reason": "No by-strike dealer exposure available."}

    ordered = by_strike.sort_values("strike").copy()
    ordered["cumulative_gamma"] = ordered["dealer_gamma_exposure"].cumsum()

    flip_rows = ordered[ordered["cumulative_gamma"].shift(1).fillna(ordered["cumulative_gamma"]) * ordered["cumulative_gamma"] <= 0]

    if not flip_rows.empty:
        gamma_flip = float(flip_rows["strike"].iloc[0])
    else:
        idx = ordered["cumulative_gamma"].abs().idxmin()
        gamma_flip = float(ordered.loc[idx, "strike"])

    spot = float(exposure_report.get("summary", {}).get("underlying_price", 0))
    distance_pct = ((gamma_flip / spot) - 1) * 100 if spot > 0 else 0

    return {
        "available": True,
        "gamma_flip": round(gamma_flip, 2),
        "distance_to_flip_pct": round(distance_pct, 2),
        "cumulative_gamma_curve": ordered,
    }


def classify_dealer_positioning_regime(
    exposure_report: dict[str, Any],
    flip_report: dict[str, Any],
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or DEFAULT_DEALER_POSITIONING_POLICY

    if not exposure_report.get("available"):
        return exposure_report

    s = exposure_report.get("summary", {})
    gamma = float(s.get("total_dealer_gamma", 0))
    delta = float(s.get("total_dealer_delta", 0))
    vega = float(s.get("total_dealer_vega", 0))

    gamma_threshold = float(policy.get("gamma_pressure_threshold", 1_000_000))
    delta_threshold = float(policy.get("delta_pressure_threshold", 1_000_000))
    vega_threshold = float(policy.get("vega_pressure_threshold", 500_000))

    drivers = []

    if gamma < -gamma_threshold:
        gamma_regime = "SHORT_GAMMA"
        drivers.append("Dealer gamma exposure is materially short.")
    elif gamma > gamma_threshold:
        gamma_regime = "LONG_GAMMA"
        drivers.append("Dealer gamma exposure is materially long.")
    else:
        gamma_regime = "NEUTRAL_GAMMA"

    if delta < -delta_threshold:
        delta_regime = "SELL_PRESSURE"
        drivers.append("Dealer delta hedge proxy indicates sell pressure.")
    elif delta > delta_threshold:
        delta_regime = "BUY_PRESSURE"
        drivers.append("Dealer delta hedge proxy indicates buy pressure.")
    else:
        delta_regime = "NEUTRAL_DELTA"

    if abs(vega) > vega_threshold:
        vega_regime = "VEGA_PRESSURE"
        drivers.append("Dealer vega exposure is elevated.")
    else:
        vega_regime = "NORMAL_VEGA"

    if gamma_regime == "SHORT_GAMMA":
        positioning_regime = "AMPLIFYING"
        hedge_bias = "Trend amplification risk"
    elif gamma_regime == "LONG_GAMMA":
        positioning_regime = "DAMPENING"
        hedge_bias = "Mean-reversion / volatility suppression"
    else:
        positioning_regime = "BALANCED"
        hedge_bias = "Balanced hedging pressure"

    distance_to_flip = abs(float(flip_report.get("distance_to_flip_pct", 0))) if flip_report.get("available") else 0
    if distance_to_flip <= 2:
        drivers.append("Spot is close to estimated gamma flip.")

    return {
        "available": True,
        "positioning_regime": positioning_regime,
        "gamma_regime": gamma_regime,
        "delta_regime": delta_regime,
        "vega_regime": vega_regime,
        "hedge_bias": hedge_bias,
        "drivers": drivers or ["Dealer positioning is balanced."],
    }


def generate_dealer_positioning_recommendations(
    regime_report: dict[str, Any],
    walls_report: dict[str, Any],
    flip_report: dict[str, Any],
) -> pd.DataFrame:
    rows = []

    gamma_regime = regime_report.get("gamma_regime", "NEUTRAL_GAMMA")
    positioning = regime_report.get("positioning_regime", "BALANCED")
    delta_regime = regime_report.get("delta_regime", "NEUTRAL_DELTA")

    if gamma_regime == "SHORT_GAMMA":
        rows.append({
            "Recommendation": "Expect Higher Intraday Volatility",
            "Priority": "High",
            "Rationale": "Dealer short gamma can amplify directional moves.",
            "Structures": "Defined-risk directional spreads, gamma-aware hedges, avoid oversized short gamma",
        })

    if gamma_regime == "LONG_GAMMA":
        rows.append({
            "Recommendation": "Expect Pinning / Mean Reversion",
            "Priority": "Medium",
            "Rationale": "Dealer long gamma can dampen realized volatility.",
            "Structures": "Range trades, iron condors, premium harvesting with controls",
        })

    if delta_regime == "BUY_PRESSURE":
        rows.append({
            "Recommendation": "Dealer Hedge Buy Pressure",
            "Priority": "Medium",
            "Rationale": "Dealer delta proxy suggests hedging demand may support upside.",
            "Structures": "Bull spreads, call calendars, put credit spreads",
        })

    if delta_regime == "SELL_PRESSURE":
        rows.append({
            "Recommendation": "Dealer Hedge Sell Pressure",
            "Priority": "Medium",
            "Rationale": "Dealer delta proxy suggests hedging demand may pressure downside.",
            "Structures": "Bear spreads, put calendars, call credit spreads",
        })

    if flip_report.get("available") and abs(float(flip_report.get("distance_to_flip_pct", 0))) <= 2:
        rows.append({
            "Recommendation": "Gamma Flip Proximity Watch",
            "Priority": "High",
            "Rationale": "Spot is close to estimated gamma flip; hedging behavior may change quickly.",
            "Structures": "Reduce short gamma, monitor breakout/breakdown confirmation",
        })

    walls_summary = walls_report.get("summary", {}) if walls_report.get("available") else {}
    if walls_summary.get("top_call_wall", 0):
        rows.append({
            "Recommendation": "Call Wall Resistance Watch",
            "Priority": "Normal",
            "Rationale": f"Top call wall near {walls_summary.get('top_call_wall')}.",
            "Structures": "Call spread targeting, overwrite review",
        })

    if walls_summary.get("top_put_wall", 0):
        rows.append({
            "Recommendation": "Put Wall Support Watch",
            "Priority": "Normal",
            "Rationale": f"Top put wall near {walls_summary.get('top_put_wall')}.",
            "Structures": "Put spread targeting, CSP review",
        })

    if not rows:
        rows.append({
            "Recommendation": "Neutral Dealer Positioning",
            "Priority": "Normal",
            "Rationale": "No major dealer pressure detected.",
            "Structures": "Balanced defined-risk structures",
        })

    return pd.DataFrame(rows)


def build_dealer_positioning_report(
    chain_data: Any,
    underlying_price: float | None = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or DEFAULT_DEALER_POSITIONING_POLICY

    exposures = calculate_dealer_exposures(
        chain_data=chain_data,
        underlying_price=underlying_price,
        policy=policy,
    )

    if not exposures.get("available"):
        return exposures

    walls = detect_dealer_walls(exposures, policy=policy)
    flip = estimate_gamma_flip(exposures)
    regime = classify_dealer_positioning_regime(exposures, flip, policy=policy)
    recommendations = generate_dealer_positioning_recommendations(regime, walls, flip)

    summary = {
        **exposures.get("summary", {}),
        "positioning_regime": regime.get("positioning_regime"),
        "gamma_regime": regime.get("gamma_regime"),
        "delta_regime": regime.get("delta_regime"),
        "vega_regime": regime.get("vega_regime"),
        "gamma_flip": flip.get("gamma_flip") if flip.get("available") else 0,
        "distance_to_flip_pct": flip.get("distance_to_flip_pct") if flip.get("available") else 0,
        "top_call_wall": walls.get("summary", {}).get("top_call_wall", 0) if walls.get("available") else 0,
        "top_put_wall": walls.get("summary", {}).get("top_put_wall", 0) if walls.get("available") else 0,
        "recommendation_count": int(len(recommendations)),
    }

    return {
        "available": True,
        "summary": summary,
        "exposures": exposures,
        "walls": walls,
        "gamma_flip": flip,
        "regime": regime,
        "recommendations": recommendations,
        "policy": policy,
    }


def summarize_dealer_positioning(report: dict[str, Any]) -> str:
    if not report.get("available"):
        return f"Dealer Positioning unavailable: {report.get('reason', 'unknown reason')}"

    s = report.get("summary", {})
    return (
        f"Dealer Positioning regime is {s.get('positioning_regime')} with "
        f"{s.get('gamma_regime')} gamma, {s.get('delta_regime')} delta, "
        f"and {s.get('vega_regime')} vega. "
        f"Estimated gamma flip is {s.get('gamma_flip')} "
        f"({s.get('distance_to_flip_pct')}% from spot). "
        f"Top call wall is {s.get('top_call_wall')} and top put wall is {s.get('top_put_wall')}."
    )
