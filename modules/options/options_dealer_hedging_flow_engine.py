"""
Sprint 11 Phase 3 — Dealer Hedging Flow Engine.

Institutional market-making analytics:
- Dealer hedge-flow proxy
- Delta-hedging pressure by strike / expiry
- Gamma-driven re-hedging pressure
- Intraday move sensitivity proxy
- Buy/sell hedge-pressure classification
- Flow regime and recommendation generation

This module does not place trades. It generates deterministic dealer hedging-flow
diagnostics from options-chain data.
"""
from __future__ import annotations

from typing import Any
import pandas as pd


DEFAULT_DEALER_HEDGING_FLOW_POLICY = {
    "contract_multiplier": 100,
    "spot_move_shock_pct": 1.0,
    "high_flow_threshold": 1_000_000,
    "medium_flow_threshold": 250_000,
    "gamma_acceleration_threshold": 500_000,
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


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def normalize_hedging_flow_chain(chain_data: Any, underlying_price: float | None = None) -> pd.DataFrame:
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

    df["dealer_spot"] = float(spot)
    df["moneyness_pct"] = ((df["strike"] / max(0.01, float(spot))) - 1.0) * 100

    return df


def calculate_hedging_flow(
    chain_data: Any,
    underlying_price: float | None = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or DEFAULT_DEALER_HEDGING_FLOW_POLICY
    df = normalize_hedging_flow_chain(chain_data, underlying_price=underlying_price)

    if df.empty:
        return {"available": False, "reason": "No options chain data available.", "chain": df}

    df = df[
        (df["open_interest"] >= float(policy.get("min_open_interest", 0)))
        & (df["volume"] >= float(policy.get("min_volume", 0)))
    ].copy()

    if df.empty:
        return {"available": False, "reason": "No option rows passed hedging-flow filters.", "chain": df}

    multiplier = float(policy.get("contract_multiplier", 100))
    shock_pct = float(policy.get("spot_move_shock_pct", 1.0)) / 100.0
    spot = float(df["dealer_spot"].iloc[0])
    shock_points = spot * shock_pct

    # Dealer proxy convention:
    # Customer long options imply dealer short options. Dealer hedge demand is modeled
    # from delta exposure plus gamma re-hedging for a hypothetical spot shock.
    direction = -1.0

    df["dealer_delta_notional"] = direction * df["delta"] * df["open_interest"] * multiplier * spot
    put_mask = df["type"].eq("put")
    df.loc[put_mask, "dealer_delta_notional"] = -1.0 * df.loc[put_mask, "delta"] * df.loc[put_mask, "open_interest"] * multiplier * spot

    df["gamma_rehedge_notional_up"] = direction * df["gamma"] * shock_points * df["open_interest"] * multiplier * spot
    df["gamma_rehedge_notional_down"] = -df["gamma_rehedge_notional_up"]

    df["net_hedge_flow_up"] = df["dealer_delta_notional"] + df["gamma_rehedge_notional_up"]
    df["net_hedge_flow_down"] = df["dealer_delta_notional"] + df["gamma_rehedge_notional_down"]
    df["absolute_flow_pressure"] = df[["net_hedge_flow_up", "net_hedge_flow_down"]].abs().max(axis=1)

    by_strike = (
        df.groupby("strike", as_index=False)
        .agg(
            dealer_delta_notional=("dealer_delta_notional", "sum"),
            gamma_rehedge_notional_up=("gamma_rehedge_notional_up", "sum"),
            gamma_rehedge_notional_down=("gamma_rehedge_notional_down", "sum"),
            net_hedge_flow_up=("net_hedge_flow_up", "sum"),
            net_hedge_flow_down=("net_hedge_flow_down", "sum"),
            absolute_flow_pressure=("absolute_flow_pressure", "sum"),
            open_interest=("open_interest", "sum"),
            volume=("volume", "sum"),
        )
        .sort_values("strike")
        .reset_index(drop=True)
    )

    by_expiry = (
        df.groupby(["expiry", "dte"], as_index=False)
        .agg(
            dealer_delta_notional=("dealer_delta_notional", "sum"),
            gamma_rehedge_notional_up=("gamma_rehedge_notional_up", "sum"),
            gamma_rehedge_notional_down=("gamma_rehedge_notional_down", "sum"),
            net_hedge_flow_up=("net_hedge_flow_up", "sum"),
            net_hedge_flow_down=("net_hedge_flow_down", "sum"),
            absolute_flow_pressure=("absolute_flow_pressure", "sum"),
            open_interest=("open_interest", "sum"),
            volume=("volume", "sum"),
        )
        .sort_values("dte")
        .reset_index(drop=True)
    )

    total_up = float(by_strike["net_hedge_flow_up"].sum())
    total_down = float(by_strike["net_hedge_flow_down"].sum())
    total_abs = float(by_strike["absolute_flow_pressure"].sum())
    total_delta = float(by_strike["dealer_delta_notional"].sum())
    total_gamma_up = float(by_strike["gamma_rehedge_notional_up"].sum())

    return {
        "available": True,
        "chain": df,
        "by_strike": by_strike,
        "by_expiry": by_expiry,
        "summary": {
            "spot": round(spot, 4),
            "shock_pct": round(shock_pct * 100, 2),
            "shock_points": round(shock_points, 4),
            "total_hedge_flow_up": round(total_up, 2),
            "total_hedge_flow_down": round(total_down, 2),
            "total_absolute_flow_pressure": round(total_abs, 2),
            "total_dealer_delta_notional": round(total_delta, 2),
            "total_gamma_rehedge_up": round(total_gamma_up, 2),
            "contract_count": int(len(df)),
            "expiry_count": int(df["expiry"].nunique()) if "expiry" in df.columns else 0,
            "strike_count": int(df["strike"].nunique()) if "strike" in df.columns else 0,
        },
        "policy": policy,
    }


def classify_hedging_flow_regime(flow_report: dict[str, Any], policy: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = policy or DEFAULT_DEALER_HEDGING_FLOW_POLICY

    if not flow_report.get("available"):
        return flow_report

    s = flow_report.get("summary", {})
    up = float(s.get("total_hedge_flow_up", 0))
    down = float(s.get("total_hedge_flow_down", 0))
    abs_flow = float(s.get("total_absolute_flow_pressure", 0))
    gamma_up = float(s.get("total_gamma_rehedge_up", 0))

    high_threshold = float(policy.get("high_flow_threshold", 1_000_000))
    medium_threshold = float(policy.get("medium_flow_threshold", 250_000))
    gamma_threshold = float(policy.get("gamma_acceleration_threshold", 500_000))

    drivers = []

    if abs_flow >= high_threshold:
        intensity = "HIGH"
        drivers.append("Absolute dealer hedge-flow pressure is high.")
    elif abs_flow >= medium_threshold:
        intensity = "MEDIUM"
        drivers.append("Absolute dealer hedge-flow pressure is moderate.")
    else:
        intensity = "LOW"

    if up > high_threshold:
        up_bias = "BUY_PRESSURE_ON_UP_MOVE"
        drivers.append("Up-move hedge-flow proxy indicates buy pressure.")
    elif up < -high_threshold:
        up_bias = "SELL_PRESSURE_ON_UP_MOVE"
        drivers.append("Up-move hedge-flow proxy indicates sell pressure.")
    else:
        up_bias = "NEUTRAL_ON_UP_MOVE"

    if down > high_threshold:
        down_bias = "BUY_PRESSURE_ON_DOWN_MOVE"
        drivers.append("Down-move hedge-flow proxy indicates buy pressure.")
    elif down < -high_threshold:
        down_bias = "SELL_PRESSURE_ON_DOWN_MOVE"
        drivers.append("Down-move hedge-flow proxy indicates sell pressure.")
    else:
        down_bias = "NEUTRAL_ON_DOWN_MOVE"

    if abs(gamma_up) >= gamma_threshold:
        acceleration = "GAMMA_ACCELERATION"
        drivers.append("Gamma re-hedging pressure is elevated.")
    else:
        acceleration = "NORMAL_REHEDGE"

    if intensity == "HIGH" and acceleration == "GAMMA_ACCELERATION":
        regime = "ACTIVE_HEDGING_PRESSURE"
    elif intensity == "MEDIUM":
        regime = "MODERATE_HEDGING_PRESSURE"
    else:
        regime = "LOW_HEDGING_PRESSURE"

    return {
        "available": True,
        "hedging_flow_regime": regime,
        "flow_intensity": intensity,
        "up_move_bias": up_bias,
        "down_move_bias": down_bias,
        "gamma_acceleration": acceleration,
        "drivers": drivers or ["Dealer hedging flow pressure is low."],
    }


def build_hedging_pressure_zones(flow_report: dict[str, Any]) -> dict[str, Any]:
    if not flow_report.get("available"):
        return flow_report

    by_strike = flow_report.get("by_strike")
    if not isinstance(by_strike, pd.DataFrame) or by_strike.empty:
        return {"available": False, "reason": "No by-strike hedging flow available."}

    zones = by_strike.copy()
    zones["pressure_rank"] = zones["absolute_flow_pressure"].rank(ascending=False, method="dense")
    zones = zones.sort_values("absolute_flow_pressure", ascending=False).reset_index(drop=True)

    top_pressure_strike = float(zones["strike"].iloc[0]) if not zones.empty else 0

    return {
        "available": True,
        "pressure_zones": zones,
        "top_pressure_strike": round(top_pressure_strike, 2),
    }


def generate_dealer_hedging_flow_recommendations(
    regime_report: dict[str, Any],
    zones_report: dict[str, Any],
) -> pd.DataFrame:
    rows = []

    regime = regime_report.get("hedging_flow_regime", "LOW_HEDGING_PRESSURE")
    up_bias = regime_report.get("up_move_bias", "NEUTRAL_ON_UP_MOVE")
    down_bias = regime_report.get("down_move_bias", "NEUTRAL_ON_DOWN_MOVE")
    acceleration = regime_report.get("gamma_acceleration", "NORMAL_REHEDGE")

    if regime == "ACTIVE_HEDGING_PRESSURE":
        rows.append({
            "Recommendation": "Active Dealer Hedge Pressure",
            "Priority": "High",
            "Rationale": "Dealer hedge-flow proxy indicates high pressure and gamma acceleration.",
            "Structures": "Defined-risk directional spreads, avoid oversized short gamma, monitor pressure strikes",
        })

    if "BUY_PRESSURE" in up_bias:
        rows.append({
            "Recommendation": "Upside Buy-Pressure Watch",
            "Priority": "Medium",
            "Rationale": "Dealer hedge-flow proxy may reinforce upside moves.",
            "Structures": "Bull call spreads, put credit spreads, momentum confirmation trades",
        })

    if "SELL_PRESSURE" in down_bias:
        rows.append({
            "Recommendation": "Downside Sell-Pressure Watch",
            "Priority": "Medium",
            "Rationale": "Dealer hedge-flow proxy may reinforce downside moves.",
            "Structures": "Bear put spreads, call credit spreads, protective puts",
        })

    if acceleration == "GAMMA_ACCELERATION":
        rows.append({
            "Recommendation": "Gamma Acceleration Risk",
            "Priority": "High",
            "Rationale": "Gamma re-hedging pressure is elevated.",
            "Structures": "Reduce short gamma, prefer defined-risk structures",
        })

    if zones_report.get("available"):
        rows.append({
            "Recommendation": "Monitor Top Hedge-Pressure Strike",
            "Priority": "Normal",
            "Rationale": f"Top hedge-pressure strike is {zones_report.get('top_pressure_strike')}.",
            "Structures": "Use pressure zones as support/resistance context",
        })

    if not rows:
        rows.append({
            "Recommendation": "Neutral Hedging Flow",
            "Priority": "Normal",
            "Rationale": "Dealer hedge-flow proxy is balanced.",
            "Structures": "Balanced defined-risk options structures",
        })

    return pd.DataFrame(rows)


def build_dealer_hedging_flow_report(
    chain_data: Any,
    underlying_price: float | None = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or DEFAULT_DEALER_HEDGING_FLOW_POLICY

    flow = calculate_hedging_flow(
        chain_data=chain_data,
        underlying_price=underlying_price,
        policy=policy,
    )

    if not flow.get("available"):
        return flow

    regime = classify_hedging_flow_regime(flow, policy=policy)
    zones = build_hedging_pressure_zones(flow)
    recommendations = generate_dealer_hedging_flow_recommendations(regime, zones)

    summary = {
        **flow.get("summary", {}),
        "hedging_flow_regime": regime.get("hedging_flow_regime"),
        "flow_intensity": regime.get("flow_intensity"),
        "up_move_bias": regime.get("up_move_bias"),
        "down_move_bias": regime.get("down_move_bias"),
        "gamma_acceleration": regime.get("gamma_acceleration"),
        "top_pressure_strike": zones.get("top_pressure_strike", 0) if zones.get("available") else 0,
        "recommendation_count": int(len(recommendations)),
    }

    return {
        "available": True,
        "summary": summary,
        "flow": flow,
        "regime": regime,
        "zones": zones,
        "recommendations": recommendations,
        "policy": policy,
    }


def summarize_dealer_hedging_flow(report: dict[str, Any]) -> str:
    if not report.get("available"):
        return f"Dealer Hedging Flow unavailable: {report.get('reason', 'unknown reason')}"

    s = report.get("summary", {})
    return (
        f"Dealer Hedging Flow regime is {s.get('hedging_flow_regime')} "
        f"with {s.get('flow_intensity')} intensity. "
        f"Up-move bias is {s.get('up_move_bias')} and down-move bias is {s.get('down_move_bias')}. "
        f"Top hedge-pressure strike is {s.get('top_pressure_strike')}."
    )
