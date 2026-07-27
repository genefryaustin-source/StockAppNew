"""
modules/options/options_greeks_validation_engine.py

Read-only Greeks Audit Engine.

Compares provider-supplied Greeks against independently calculated
Black-Scholes Greeks using:
- underlying price
- strike
- DTE / expiry
- IV
- option type

This module does NOT submit, cancel, or modify orders.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from math import erf, exp, log, pi, sqrt
from typing import Any

import pandas as pd


DEFAULT_RISK_FREE_RATE = 0.045
DEFAULT_DIVIDEND_YIELD = 0.0

# Base tolerances. The audit also applies adaptive tolerance widening
# for contracts where Black-Scholes and provider methodology commonly diverge:
# near-expiration, extreme-IV, and very deep ITM/OTM contracts.
DELTA_WARN_TOLERANCE = 0.08
DELTA_FAIL_TOLERANCE = 0.15

GAMMA_WARN_TOLERANCE = 0.035
GAMMA_FAIL_TOLERANCE = 0.075

THETA_WARN_TOLERANCE = 0.25
THETA_FAIL_TOLERANCE = 0.50

VEGA_WARN_TOLERANCE = 0.25
VEGA_FAIL_TOLERANCE = 0.50


@dataclass
class GreeksAuditRow:
    option_symbol: str
    option_type: str
    strike: float
    expiry: str
    dte: float
    underlying_price: float
    iv: float
    provider_delta: float | None
    calc_delta: float | None
    delta_diff: float | None
    provider_gamma: float | None
    calc_gamma: float | None
    gamma_diff: float | None
    provider_theta: float | None
    calc_theta: float | None
    theta_diff: float | None
    provider_vega: float | None
    calc_vega: float | None
    vega_diff: float | None
    status: str
    message: str


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + erf(x / sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    return exp(-0.5 * x * x) / sqrt(2.0 * pi)


def _to_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None:
            return default
        if isinstance(value, str) and value.strip() == "":
            return default
        val = float(value)
        if pd.isna(val):
            return default
        return val
    except Exception:
        return default


def _normalize_type(value: Any, option_symbol: str = "") -> str:
    text = str(value or "").lower().strip()
    if text in {"call", "calls", "c"}:
        return "call"
    if text in {"put", "puts", "p"}:
        return "put"

    sym = str(option_symbol or "").upper()
    if len(sym) >= 9:
        cp = sym[-9]
        if cp == "C":
            return "call"
        if cp == "P":
            return "put"

    return ""


def _extract_chain_frame(chain_data: dict[str, Any]) -> pd.DataFrame:
    if not isinstance(chain_data, dict):
        return pd.DataFrame()

    all_rows = chain_data.get("all_rows")
    if isinstance(all_rows, pd.DataFrame) and not all_rows.empty:
        return all_rows.copy()

    frames: list[pd.DataFrame] = []
    chain = chain_data.get("chain", {}) or {}

    if isinstance(chain, dict):
        for expiry, bucket in chain.items():
            if not isinstance(bucket, dict):
                continue

            for side_name in ("calls", "puts"):
                df = bucket.get(side_name)
                if isinstance(df, pd.DataFrame) and not df.empty:
                    temp = df.copy()
                    if "expiry" not in temp.columns:
                        temp["expiry"] = expiry
                    if "expiration" not in temp.columns:
                        temp["expiration"] = expiry
                    if "type" not in temp.columns:
                        temp["type"] = "call" if side_name == "calls" else "put"
                    frames.append(temp)

    if frames:
        return pd.concat(frames, ignore_index=True)

    contracts = chain_data.get("contracts")
    if isinstance(contracts, list) and contracts:
        return pd.DataFrame(contracts)

    return pd.DataFrame()


def _black_scholes_greeks(
    option_type: str,
    underlying_price: float,
    strike: float,
    dte: float,
    iv: float,
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
    dividend_yield: float = DEFAULT_DIVIDEND_YIELD,
) -> dict[str, float | None]:
    """
    Return Black-Scholes Greeks.

    Notes:
    - theta is returned per day
    - vega is returned per 1 volatility point, matching common option-chain display convention
    """
    option_type = _normalize_type(option_type)

    if option_type not in {"call", "put"}:
        return {"delta": None, "gamma": None, "theta": None, "vega": None}

    if underlying_price <= 0 or strike <= 0 or dte <= 0 or iv <= 0:
        return {"delta": None, "gamma": None, "theta": None, "vega": None}

    # If provider supplies IV as percent (example 52.7), normalize to decimal.
    sigma = iv / 100.0 if iv > 3.0 else iv
    if sigma <= 0:
        return {"delta": None, "gamma": None, "theta": None, "vega": None}

    t = max(dte / 365.0, 1.0 / 365.0)
    s = underlying_price
    k = strike
    r = risk_free_rate
    q = dividend_yield

    d1 = (log(s / k) + (r - q + 0.5 * sigma * sigma) * t) / (sigma * sqrt(t))
    d2 = d1 - sigma * sqrt(t)

    nd1 = _norm_pdf(d1)
    discount_q = exp(-q * t)
    discount_r = exp(-r * t)

    if option_type == "call":
        delta = discount_q * _norm_cdf(d1)
        theta_annual = (
            -s * discount_q * nd1 * sigma / (2.0 * sqrt(t))
            - r * k * discount_r * _norm_cdf(d2)
            + q * s * discount_q * _norm_cdf(d1)
        )
    else:
        delta = discount_q * (_norm_cdf(d1) - 1.0)
        theta_annual = (
            -s * discount_q * nd1 * sigma / (2.0 * sqrt(t))
            + r * k * discount_r * _norm_cdf(-d2)
            - q * s * discount_q * _norm_cdf(-d1)
        )

    gamma = discount_q * nd1 / (s * sigma * sqrt(t))
    theta = theta_annual / 365.0
    vega = s * discount_q * nd1 * sqrt(t) / 100.0

    return {
        "delta": delta,
        "gamma": gamma,
        "theta": theta,
        "vega": vega,
    }


def _adaptive_tolerances(
    metric: str,
    dte: float | None = None,
    iv: float | None = None,
    underlying_price: float | None = None,
    strike: float | None = None,
) -> tuple[float, float, list[str]]:
    """
    Return warning/fail tolerances adjusted for edge cases.

    Near-expiration, extreme-IV, and far ITM/OTM contracts often produce
    legitimate methodology differences across providers. Those should usually
    be WARNs unless the discrepancy is extreme.
    """
    reasons: list[str] = []

    if metric == "delta":
        warn = DELTA_WARN_TOLERANCE
        fail = DELTA_FAIL_TOLERANCE
    elif metric == "gamma":
        warn = GAMMA_WARN_TOLERANCE
        fail = GAMMA_FAIL_TOLERANCE
    elif metric == "theta":
        warn = THETA_WARN_TOLERANCE
        fail = THETA_FAIL_TOLERANCE
    elif metric == "vega":
        warn = VEGA_WARN_TOLERANCE
        fail = VEGA_FAIL_TOLERANCE
    else:
        return 0.0, 0.0, reasons

    try:
        dte_val = float(dte) if dte is not None else None
    except Exception:
        dte_val = None

    try:
        iv_val = float(iv) if iv is not None else None
    except Exception:
        iv_val = None

    try:
        s = float(underlying_price) if underlying_price is not None else None
        k = float(strike) if strike is not None else None
    except Exception:
        s = None
        k = None

    # Normalize IV if a provider sends percent form.
    iv_decimal = iv_val / 100.0 if iv_val is not None and iv_val > 3.0 else iv_val

    near_expiry = dte_val is not None and dte_val <= 3
    extreme_iv = iv_decimal is not None and iv_decimal >= 2.0
    far_moneyness = False
    if s is not None and k is not None and s > 0:
        far_moneyness = abs(k / s - 1.0) >= 0.40

    if near_expiry:
        reasons.append("near-expiration")
    if extreme_iv:
        reasons.append("extreme-IV")
    if far_moneyness:
        reasons.append("far-moneyness")

    # Delta is most prone to provider/model differences near expiry and with
    # extreme IV. The widening below turns the previous false positives into
    # warnings/passes without hiding large breaks.
    if metric == "delta":
        if near_expiry or extreme_iv or far_moneyness:
            warn = max(warn, 0.10)
            fail = max(fail, 0.25)

        if near_expiry and extreme_iv:
            warn = max(warn, 0.12)
            fail = max(fail, 0.30)

    # Gamma and Vega are often tiny for very deep ITM/OTM contracts. Small
    # absolute differences can appear large in relative terms, so use wider
    # absolute thresholds in those edge cases.
    elif metric in {"gamma", "vega"}:
        if near_expiry or extreme_iv or far_moneyness:
            warn *= 1.5
            fail *= 1.5

    # Theta can vary significantly depending on calendar-day vs trading-day
    # convention and rates/dividends. Widen modestly for near-expiry options.
    elif metric == "theta":
        if near_expiry or extreme_iv:
            warn *= 1.5
            fail *= 1.5

    return warn, fail, reasons


def _status_for_diff(
    metric: str,
    diff: float | None,
    dte: float | None = None,
    iv: float | None = None,
    underlying_price: float | None = None,
    strike: float | None = None,
) -> tuple[str, str]:
    if diff is None:
        return "WARN", "Unable to compare; missing provider or calculated value."

    adiff = abs(diff)
    warn_tolerance, fail_tolerance, reasons = _adaptive_tolerances(
        metric=metric,
        dte=dte,
        iv=iv,
        underlying_price=underlying_price,
        strike=strike,
    )

    label = metric.capitalize()
    context = f" Adaptive context: {', '.join(reasons)}." if reasons else ""

    if adiff >= fail_tolerance:
        return "FAIL", (
            f"{label} difference {adiff:.4f} exceeds fail tolerance "
            f"{fail_tolerance:.4f}.{context}"
        )

    if adiff >= warn_tolerance:
        return "WARN", (
            f"{label} difference {adiff:.4f} exceeds warning tolerance "
            f"{warn_tolerance:.4f}.{context}"
        )

    return "PASS", (
        f"{label} difference is within tolerance "
        f"({adiff:.4f} <= {warn_tolerance:.4f}).{context}"
    )


def audit_chain_greeks(
    chain_data: dict[str, Any],
    max_rows: int = 250,
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
    dividend_yield: float = DEFAULT_DIVIDEND_YIELD,
) -> dict[str, Any]:
    df = _extract_chain_frame(chain_data)

    result: dict[str, Any] = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "provider": chain_data.get("provider") if isinstance(chain_data, dict) else None,
        "source": chain_data.get("source") if isinstance(chain_data, dict) else None,
        "rows_available": int(len(df)) if isinstance(df, pd.DataFrame) else 0,
        "rows_audited": 0,
        "totals": {"PASS": 0, "WARN": 0, "FAIL": 0},
        "rows": [],
        "notes": [],
    }

    if df.empty:
        result["notes"].append("No chain rows available for Greeks audit.")
        return result

    required = ["strike", "iv", "delta", "gamma", "theta", "vega"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        result["notes"].append(f"Missing columns: {missing}")

    if "option_symbol" not in df.columns:
        df["option_symbol"] = ""

    if "type" not in df.columns:
        df["type"] = ""

    if "expiry" not in df.columns and "expiration" in df.columns:
        df["expiry"] = df["expiration"]

    if "underlying_price" not in df.columns:
        result["notes"].append("No underlying_price column found. Greeks audit requires underlying price.")
        return result

    work = df.copy()
    work["strike_num"] = pd.to_numeric(work.get("strike"), errors="coerce")
    work["underlying_num"] = pd.to_numeric(work.get("underlying_price"), errors="coerce")
    work["iv_num"] = pd.to_numeric(work.get("iv"), errors="coerce")
    work["dte_num"] = pd.to_numeric(work.get("dte"), errors="coerce")

    work = work.dropna(subset=["strike_num", "underlying_num", "iv_num", "dte_num"])
    work = work[(work["strike_num"] > 0) & (work["underlying_num"] > 0) & (work["iv_num"] > 0) & (work["dte_num"] > 0)]

    if work.empty:
        result["notes"].append("No rows with usable strike, underlying price, IV, and DTE.")
        return result

    # Prioritize contracts near ATM because they are most informative for Greek validation.
    work["moneyness_gap"] = (work["strike_num"] - work["underlying_num"]).abs()
    work = work.sort_values(["moneyness_gap", "dte_num"]).head(max_rows)

    rows: list[GreeksAuditRow] = []

    for _, row in work.iterrows():
        option_symbol = str(row.get("option_symbol") or "")
        option_type = _normalize_type(row.get("type"), option_symbol)
        strike = float(row["strike_num"])
        underlying = float(row["underlying_num"])
        iv = float(row["iv_num"])
        dte = float(row["dte_num"])
        expiry = str(row.get("expiry") or row.get("expiration") or "")

        calc = _black_scholes_greeks(
            option_type=option_type,
            underlying_price=underlying,
            strike=strike,
            dte=dte,
            iv=iv,
            risk_free_rate=risk_free_rate,
            dividend_yield=dividend_yield,
        )

        provider_delta = _to_float(row.get("delta"))
        provider_gamma = _to_float(row.get("gamma"))
        provider_theta = _to_float(row.get("theta"))
        provider_vega = _to_float(row.get("vega"))

        calc_delta = calc.get("delta")
        calc_gamma = calc.get("gamma")
        calc_theta = calc.get("theta")
        calc_vega = calc.get("vega")

        delta_diff = provider_delta - calc_delta if provider_delta is not None and calc_delta is not None else None
        gamma_diff = provider_gamma - calc_gamma if provider_gamma is not None and calc_gamma is not None else None
        theta_diff = provider_theta - calc_theta if provider_theta is not None and calc_theta is not None else None
        vega_diff = provider_vega - calc_vega if provider_vega is not None and calc_vega is not None else None

        metric_statuses = [
            _status_for_diff("delta", delta_diff, dte=dte, iv=iv, underlying_price=underlying, strike=strike),
            _status_for_diff("gamma", gamma_diff, dte=dte, iv=iv, underlying_price=underlying, strike=strike),
            _status_for_diff("theta", theta_diff, dte=dte, iv=iv, underlying_price=underlying, strike=strike),
            _status_for_diff("vega", vega_diff, dte=dte, iv=iv, underlying_price=underlying, strike=strike),
        ]

        status = "PASS"
        if any(s == "FAIL" for s, _ in metric_statuses):
            status = "FAIL"
        elif any(s == "WARN" for s, _ in metric_statuses):
            status = "WARN"

        messages = [m for _, m in metric_statuses]
        message = " | ".join(messages)

        rows.append(GreeksAuditRow(
            option_symbol=option_symbol,
            option_type=option_type,
            strike=strike,
            expiry=expiry,
            dte=dte,
            underlying_price=underlying,
            iv=iv,
            provider_delta=provider_delta,
            calc_delta=calc_delta,
            delta_diff=delta_diff,
            provider_gamma=provider_gamma,
            calc_gamma=calc_gamma,
            gamma_diff=gamma_diff,
            provider_theta=provider_theta,
            calc_theta=calc_theta,
            theta_diff=theta_diff,
            provider_vega=provider_vega,
            calc_vega=calc_vega,
            vega_diff=vega_diff,
            status=status,
            message=message,
        ))

    result["rows"] = [asdict(r) for r in rows]
    result["rows_audited"] = len(rows)

    for row in rows:
        result["totals"][row.status] = result["totals"].get(row.status, 0) + 1

    result["finished_at"] = datetime.now(timezone.utc).isoformat()

    return result


def run_greeks_validation(
    ticker: str = "SPY",
    expiration: str | None = None,
    max_rows: int = 250,
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
    dividend_yield: float = DEFAULT_DIVIDEND_YIELD,
) -> dict[str, Any]:
    from modules.options.options_data_service import get_options_chain

    try:
        chain_data = get_options_chain(ticker, expiration=expiration)
    except TypeError:
        chain_data = get_options_chain(ticker)

    result = audit_chain_greeks(
        chain_data=chain_data,
        max_rows=max_rows,
        risk_free_rate=risk_free_rate,
        dividend_yield=dividend_yield,
    )

    result["ticker"] = ticker
    result["expiration"] = expiration
    result["risk_free_rate"] = risk_free_rate
    result["dividend_yield"] = dividend_yield

    return result


def greeks_audit_frame(result: dict[str, Any]) -> pd.DataFrame:
    rows = result.get("rows", []) if isinstance(result, dict) else []
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)
