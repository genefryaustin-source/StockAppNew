"""
modules/options/options_dealer_exposure_engine.py

Phase 2 Options Dealer Analytics Engine.

Adds institutional/dealer positioning analytics using the existing options chain:
- Gamma Exposure (GEX)
- Delta Exposure (DEX)
- Gamma walls
- Delta walls
- Zero-gamma estimate
- Pin-risk zones
- Dealer hedging pressure
- Expiration-level exposure

No new API keys required. This engine uses the same MarketData/Finnhub chain
already loaded by modules.options.options_data_service.get_options_chain.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any
import math

import pandas as pd


CONTRACT_MULTIPLIER = 100


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, float) and math.isnan(value):
            return default
        return float(value)
    except Exception:
        return default


def _side(value: Any) -> str:
    s = str(value or "").lower()
    if s in {"c", "call", "calls"}:
        return "call"
    if s in {"p", "put", "puts"}:
        return "put"
    return s


def _all_chain_rows(chain_data: dict[str, Any]) -> pd.DataFrame:
    """Normalize chain payloads from both options_data_service and flow_service."""
    if not isinstance(chain_data, dict):
        return pd.DataFrame()

    raw = chain_data.get("all_rows")
    if isinstance(raw, pd.DataFrame) and not raw.empty:
        return _normalize_columns(raw.copy())
    if raw is not None:
        try:
            df = pd.DataFrame(raw)
            if not df.empty:
                return _normalize_columns(df)
        except Exception:
            pass

    raw = chain_data.get("raw_df")
    if isinstance(raw, pd.DataFrame) and not raw.empty:
        return _normalize_columns(raw.copy())
    if raw is not None:
        try:
            df = pd.DataFrame(raw)
            if not df.empty:
                return _normalize_columns(df)
        except Exception:
            pass

    rows: list[dict[str, Any]] = []
    chains = chain_data.get("chain") or chain_data.get("chains") or {}
    for expiry, block in chains.items():
        if not isinstance(block, dict):
            continue
        calls = block.get("calls", pd.DataFrame())
        puts = block.get("puts", pd.DataFrame())
        for df_like, opt_type in [(calls, "call"), (puts, "put")]:
            try:
                df = df_like if isinstance(df_like, pd.DataFrame) else pd.DataFrame(df_like)
                if df.empty:
                    continue
                df = df.copy()
                if "expiry" not in df.columns:
                    df["expiry"] = expiry
                if "type" not in df.columns and "side" not in df.columns:
                    df["type"] = opt_type
                rows.extend(df.to_dict("records"))
            except Exception:
                continue

    return _normalize_columns(pd.DataFrame(rows)) if rows else pd.DataFrame()


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    rename = {
        "optionSymbol": "option_symbol",
        "openInterest": "open_interest",
        "openInterest": "open_interest",
        "impliedVolatility": "iv",
        "lastPrice": "last",
        "side": "type",
    }
    for old, new in rename.items():
        if old in df.columns and new not in df.columns:
            df = df.rename(columns={old: new})

    if "type" in df.columns:
        df["type"] = df["type"].apply(_side)
    elif "option_symbol" in df.columns:
        df["type"] = df["option_symbol"].astype(str).str.extract(r"([CP])\d{8}", expand=False).map({"C": "call", "P": "put"}).fillna("")

    for col in ["strike", "open_interest", "volume", "gamma", "delta", "iv", "last", "bid", "ask"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        else:
            df[col] = 0.0

    if "expiry" not in df.columns:
        df["expiry"] = ""
    if "option_symbol" not in df.columns:
        df["option_symbol"] = ""

    return df


@dataclass
class DealerExposureReport:
    ticker: str
    spot: float
    total_gex: float
    total_dex: float
    call_gex: float
    put_gex: float
    call_dex: float
    put_dex: float
    net_gamma_state: str
    hedging_pressure: str
    zero_gamma: float | None
    gamma_wall_call: float | None
    gamma_wall_put: float | None
    strongest_wall: float | None
    pin_risk_strike: float | None
    pin_risk_score: float
    gamma_by_strike: list[dict[str, Any]]
    delta_by_strike: list[dict[str, Any]]
    expiration_exposure: list[dict[str, Any]]
    top_gamma_contracts: list[dict[str, Any]]
    top_delta_contracts: list[dict[str, Any]]
    notes: list[str]


def build_dealer_exposure_report(ticker: str, chain_data: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build full Phase 2 dealer exposure report for one ticker."""
    if chain_data is None:
        try:
            from modules.options.options_data_service import get_options_chain
            chain_data = get_options_chain(ticker)
        except Exception as exc:
            return {"ticker": ticker.upper(), "error": str(exc)}

    if not isinstance(chain_data, dict):
        return {"ticker": ticker.upper(), "error": "Invalid chain payload"}
    if "error" in chain_data:
        return {"ticker": ticker.upper(), "error": chain_data.get("error")}

    spot = _num(chain_data.get("spot") or chain_data.get("underlying_price") or chain_data.get("lastTradePrice"))
    df = _all_chain_rows(chain_data)
    if df.empty:
        return {"ticker": ticker.upper(), "error": "No chain rows available for dealer exposure analysis"}
    if spot <= 0:
        # Fallback: estimate spot from median strike around active contracts.
        spot = _num(df["strike"].median())

    df = df[df["strike"] > 0].copy()
    if df.empty:
        return {"ticker": ticker.upper(), "error": "No valid strikes available"}

    # Dealer convention approximation:
    # Customer long calls/puts imply dealer short option inventory. Since we do not
    # know opening buyer/seller side from chain-only data, report exposure as
    # street/open-interest pressure. Calls contribute positive gamma pressure;
    # puts are shown as negative gamma pressure to identify put walls/negative-gamma zones.
    df["oi"] = df["open_interest"].fillna(0).clip(lower=0)
    df["gamma_abs"] = df["gamma"].fillna(0).abs()
    df["delta"] = df["delta"].fillna(0)
    df["notional_base"] = spot * CONTRACT_MULTIPLIER * df["oi"]
    df["gamma_exposure"] = df["gamma_abs"] * df["notional_base"] * spot / 100.0
    df.loc[df["type"] == "put", "gamma_exposure"] *= -1
    df["delta_exposure"] = df["delta"] * df["notional_base"]

    calls = df[df["type"] == "call"]
    puts = df[df["type"] == "put"]
    call_gex = float(calls["gamma_exposure"].sum()) if not calls.empty else 0.0
    put_gex = float(puts["gamma_exposure"].sum()) if not puts.empty else 0.0
    total_gex = call_gex + put_gex
    call_dex = float(calls["delta_exposure"].sum()) if not calls.empty else 0.0
    put_dex = float(puts["delta_exposure"].sum()) if not puts.empty else 0.0
    total_dex = call_dex + put_dex

    gamma_by_strike_df = _exposure_by_strike(df, "gamma_exposure")
    delta_by_strike_df = _exposure_by_strike(df, "delta_exposure")
    expiration_df = _exposure_by_expiration(df)

    zero_gamma = _estimate_zero_gamma(gamma_by_strike_df, spot)
    gamma_wall_call = _wall(calls, positive=True)
    gamma_wall_put = _wall(puts, positive=False)
    strongest_wall = _strongest_wall(gamma_by_strike_df)
    pin_strike, pin_score = _pin_risk(df, spot)

    abs_total_gex = abs(total_gex)
    net_gamma_state = "Positive Gamma" if total_gex > 0 else "Negative Gamma" if total_gex < 0 else "Neutral Gamma"
    if abs_total_gex < 1_000_000:
        hedging = "Low dealer gamma pressure"
    elif total_gex > 0:
        hedging = "Stabilizing / mean-reversion pressure"
    else:
        hedging = "Destabilizing / momentum-amplifying pressure"

    notes = []
    if zero_gamma:
        notes.append(f"Estimated zero-gamma level near ${zero_gamma:,.2f}.")
    if gamma_wall_call:
        notes.append(f"Largest call gamma wall near ${gamma_wall_call:,.2f}.")
    if gamma_wall_put:
        notes.append(f"Largest put gamma wall near ${gamma_wall_put:,.2f}.")
    if pin_strike:
        notes.append(f"Highest pin-risk strike near ${pin_strike:,.2f}.")
    notes.append("Dealer analytics are chain-derived estimates; opening/closing trade direction requires live flow data.")

    report = DealerExposureReport(
        ticker=ticker.upper(),
        spot=round(float(spot), 4),
        total_gex=round(total_gex, 2),
        total_dex=round(total_dex, 2),
        call_gex=round(call_gex, 2),
        put_gex=round(put_gex, 2),
        call_dex=round(call_dex, 2),
        put_dex=round(put_dex, 2),
        net_gamma_state=net_gamma_state,
        hedging_pressure=hedging,
        zero_gamma=round(zero_gamma, 2) if zero_gamma else None,
        gamma_wall_call=round(gamma_wall_call, 2) if gamma_wall_call else None,
        gamma_wall_put=round(gamma_wall_put, 2) if gamma_wall_put else None,
        strongest_wall=round(strongest_wall, 2) if strongest_wall else None,
        pin_risk_strike=round(pin_strike, 2) if pin_strike else None,
        pin_risk_score=round(pin_score, 1),
        gamma_by_strike=gamma_by_strike_df.to_dict("records"),
        delta_by_strike=delta_by_strike_df.to_dict("records"),
        expiration_exposure=expiration_df.to_dict("records"),
        top_gamma_contracts=_top_contracts(df, "gamma_exposure"),
        top_delta_contracts=_top_contracts(df, "delta_exposure"),
        notes=notes,
    )
    return asdict(report)


def _exposure_by_strike(df: pd.DataFrame, exposure_col: str) -> pd.DataFrame:
    grouped = df.groupby("strike", dropna=False).agg(
        total_exposure=(exposure_col, "sum"),
        abs_exposure=(exposure_col, lambda s: float(s.abs().sum())),
        call_oi=("oi", lambda s: 0.0),
    ).reset_index()

    call_oi = df[df["type"] == "call"].groupby("strike")["oi"].sum()
    put_oi = df[df["type"] == "put"].groupby("strike")["oi"].sum()
    grouped["call_oi"] = grouped["strike"].map(call_oi).fillna(0).astype(float)
    grouped["put_oi"] = grouped["strike"].map(put_oi).fillna(0).astype(float)
    grouped["net_oi"] = grouped["call_oi"] - grouped["put_oi"]
    grouped = grouped.sort_values("strike")
    return grouped.round(4)


def _exposure_by_expiration(df: pd.DataFrame) -> pd.DataFrame:
    if "expiry" not in df.columns:
        return pd.DataFrame()
    grouped = df.groupby("expiry", dropna=False).agg(
        gamma_exposure=("gamma_exposure", "sum"),
        delta_exposure=("delta_exposure", "sum"),
        total_oi=("oi", "sum"),
        contracts=("option_symbol", "count"),
    ).reset_index()
    grouped["abs_gamma"] = grouped["gamma_exposure"].abs()
    return grouped.sort_values("abs_gamma", ascending=False).round(2)


def _estimate_zero_gamma(gamma_by_strike: pd.DataFrame, spot: float) -> float | None:
    if gamma_by_strike.empty or "total_exposure" not in gamma_by_strike.columns:
        return None
    g = gamma_by_strike.sort_values("strike").copy()
    strikes = g["strike"].astype(float).tolist()
    exposures = g["total_exposure"].astype(float).tolist()
    for i in range(len(strikes) - 1):
        e1, e2 = exposures[i], exposures[i + 1]
        if e1 == 0:
            return strikes[i]
        if (e1 < 0 < e2) or (e1 > 0 > e2):
            s1, s2 = strikes[i], strikes[i + 1]
            # linear interpolation
            return s1 + (0 - e1) * (s2 - s1) / ((e2 - e1) or 1)
    # fallback: nearest strike where net gamma is closest to zero, preferably near spot
    g["zero_distance"] = g["total_exposure"].abs()
    g["spot_distance"] = (g["strike"] - spot).abs()
    row = g.sort_values(["zero_distance", "spot_distance"]).head(1)
    if row.empty:
        return None
    return float(row.iloc[0]["strike"])


def _wall(df: pd.DataFrame, positive: bool = True) -> float | None:
    if df.empty:
        return None
    d = df.copy()
    d["abs_gex"] = d["gamma_exposure"].abs()
    grouped = d.groupby("strike")["abs_gex"].sum().reset_index().sort_values("abs_gex", ascending=False)
    if grouped.empty:
        return None
    return float(grouped.iloc[0]["strike"])


def _strongest_wall(gamma_by_strike: pd.DataFrame) -> float | None:
    if gamma_by_strike.empty:
        return None
    row = gamma_by_strike.sort_values("abs_exposure", ascending=False).head(1)
    return float(row.iloc[0]["strike"]) if not row.empty else None


def _pin_risk(df: pd.DataFrame, spot: float) -> tuple[float | None, float]:
    if df.empty or spot <= 0:
        return None, 0.0
    g = df.groupby("strike").agg(total_oi=("oi", "sum")).reset_index()
    g["distance_pct"] = ((g["strike"] - spot).abs() / spot).replace([math.inf], 999)
    nearby = g[g["distance_pct"] <= 0.03].copy()
    if nearby.empty:
        nearby = g.copy()
    if nearby.empty:
        return None, 0.0
    max_oi = float(g["total_oi"].max() or 1)
    nearby["pin_score"] = (nearby["total_oi"] / max_oi * 70.0) + ((0.03 - nearby["distance_pct"].clip(upper=0.03)) / 0.03 * 30.0)
    row = nearby.sort_values("pin_score", ascending=False).head(1)
    return float(row.iloc[0]["strike"]), float(row.iloc[0]["pin_score"])


def _top_contracts(df: pd.DataFrame, exposure_col: str, limit: int = 20) -> list[dict[str, Any]]:
    if df.empty or exposure_col not in df.columns:
        return []
    d = df.copy()
    d["abs_exposure"] = d[exposure_col].abs()
    cols = ["option_symbol", "type", "expiry", "strike", "open_interest", "volume", "delta", "gamma", exposure_col, "abs_exposure"]
    cols = [c for c in cols if c in d.columns]
    return d.sort_values("abs_exposure", ascending=False).head(limit)[cols].round(4).to_dict("records")
