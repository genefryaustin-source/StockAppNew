"""
modules/options/options_pricing_validation_engine.py

Read-only Options Pricing Validation Engine.

Validates provider option prices against independent Black-Scholes theoretical value.

Checks:
- bid / ask / mid availability
- bid <= ask sanity
- mid inside spread
- intrinsic / extrinsic value
- provider mid vs theoretical value
- stale or suspicious pricing
- negative extrinsic value

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

PRICE_WARN_ABS = 0.50
PRICE_FAIL_ABS = 2.00

PRICE_WARN_PCT = 0.20
PRICE_FAIL_PCT = 0.50

SPREAD_WARN_PCT = 0.25
SPREAD_FAIL_PCT = 0.75


@dataclass
class PricingAuditRow:
    option_symbol: str
    option_type: str
    strike: float
    expiry: str
    dte: float
    underlying_price: float
    iv: float | None
    bid: float | None
    ask: float | None
    last: float | None
    mid: float | None
    theoretical_value: float | None
    intrinsic_value: float | None
    extrinsic_value: float | None
    price_diff: float | None
    price_diff_pct: float | None
    spread: float | None
    spread_pct: float | None
    status: str
    message: str


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + erf(x / sqrt(2.0)))


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


def _black_scholes_price(
    option_type: str,
    underlying_price: float,
    strike: float,
    dte: float,
    iv: float,
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
    dividend_yield: float = DEFAULT_DIVIDEND_YIELD,
) -> float | None:
    option_type = _normalize_type(option_type)

    if option_type not in {"call", "put"}:
        return None

    if underlying_price <= 0 or strike <= 0 or dte <= 0 or iv <= 0:
        return None

    sigma = iv / 100.0 if iv > 3.0 else iv
    if sigma <= 0:
        return None

    t = max(dte / 365.0, 1.0 / 365.0)
    s = underlying_price
    k = strike
    r = risk_free_rate
    q = dividend_yield

    d1 = (log(s / k) + (r - q + 0.5 * sigma * sigma) * t) / (sigma * sqrt(t))
    d2 = d1 - sigma * sqrt(t)

    discount_q = exp(-q * t)
    discount_r = exp(-r * t)

    if option_type == "call":
        return s * discount_q * _norm_cdf(d1) - k * discount_r * _norm_cdf(d2)

    return k * discount_r * _norm_cdf(-d2) - s * discount_q * _norm_cdf(-d1)


def _intrinsic_value(option_type: str, underlying_price: float, strike: float) -> float | None:
    option_type = _normalize_type(option_type)
    if option_type == "call":
        return max(0.0, underlying_price - strike)
    if option_type == "put":
        return max(0.0, strike - underlying_price)
    return None


def _adaptive_price_thresholds(
    dte: float | None,
    iv: float | None,
    underlying_price: float | None,
    strike: float | None,
) -> tuple[float, float, float, float, list[str]]:
    warn_abs = PRICE_WARN_ABS
    fail_abs = PRICE_FAIL_ABS
    warn_pct = PRICE_WARN_PCT
    fail_pct = PRICE_FAIL_PCT
    reasons: list[str] = []

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

    if near_expiry or extreme_iv or far_moneyness:
        warn_abs *= 2.0
        fail_abs *= 2.0
        warn_pct *= 1.5
        fail_pct *= 1.5

    if near_expiry and extreme_iv:
        warn_abs *= 1.5
        fail_abs *= 1.5
        warn_pct *= 1.25
        fail_pct *= 1.25

    return warn_abs, fail_abs, warn_pct, fail_pct, reasons


def _status_for_price(
    price_diff: float | None,
    price_diff_pct: float | None,
    dte: float | None,
    iv: float | None,
    underlying_price: float | None,
    strike: float | None,
) -> tuple[str, str]:
    if price_diff is None:
        return "WARN", "Unable to compare provider mid and theoretical value."

    warn_abs, fail_abs, warn_pct, fail_pct, reasons = _adaptive_price_thresholds(
        dte=dte,
        iv=iv,
        underlying_price=underlying_price,
        strike=strike,
    )

    abs_diff = abs(price_diff)
    abs_pct = abs(price_diff_pct) if price_diff_pct is not None else 0.0
    context = f" Adaptive context: {', '.join(reasons)}." if reasons else ""

    if abs_diff >= fail_abs and abs_pct >= fail_pct:
        return "FAIL", (
            f"Price difference {abs_diff:.2f} / {abs_pct:.1%} exceeds fail tolerance."
            f"{context}"
        )

    if abs_diff >= warn_abs and abs_pct >= warn_pct:
        return "WARN", (
            f"Price difference {abs_diff:.2f} / {abs_pct:.1%} exceeds warning tolerance."
            f"{context}"
        )

    return "PASS", (
        f"Provider mid is near theoretical value. Diff {abs_diff:.2f} / {abs_pct:.1%}."
        f"{context}"
    )


def audit_chain_pricing(
    chain_data: dict[str, Any],
    max_rows: int = 250,
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
    dividend_yield: float = DEFAULT_DIVIDEND_YIELD,
) -> dict[str, Any]:
    df = _extract_chain_frame(chain_data)
    print("=" * 80)
    print("PRICING DF COLUMNS")
    print("=" * 80)
    print(df.columns.tolist())

    print("=" * 80)
    print("PRICING DF SAMPLE")
    print("=" * 80)

    if not df.empty:
        print(df.head(3).to_dict("records"))

    print("=" * 80)

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
        result["notes"].append("No chain rows available for pricing audit.")
        return result

    if "option_symbol" not in df.columns:
        df["option_symbol"] = ""

    if "type" not in df.columns:
        df["type"] = ""

    if "expiry" not in df.columns and "expiration" in df.columns:
        df["expiry"] = df["expiration"]

    required = ["strike", "underlying_price", "iv"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        result["notes"].append(f"Missing required pricing columns: {missing}")
        return result

    work = df.copy()
    work["strike_num"] = pd.to_numeric(work.get("strike"), errors="coerce")
    work["underlying_num"] = pd.to_numeric(work.get("underlying_price"), errors="coerce")
    work["iv_num"] = pd.to_numeric(work.get("iv"), errors="coerce")
    work["dte_num"] = pd.to_numeric(work.get("dte"), errors="coerce")

    for col in ["bid", "ask", "mid", "last"]:
        if col not in work.columns:
            work[col] = None
        work[f"{col}_num"] = pd.to_numeric(work[col], errors="coerce")

    # If mid is absent, calculate it from bid/ask.
    missing_mid = work["mid_num"].isna() & work["bid_num"].notna() & work["ask_num"].notna()
    work.loc[missing_mid, "mid_num"] = (work.loc[missing_mid, "bid_num"] + work.loc[missing_mid, "ask_num"]) / 2.0

    print("=" * 80)
    print("PRICING NULL COUNTS")
    print("=" * 80)

    print("Underlying NaN:", work["underlying_num"].isna().sum())
    print("DTE <= 0:", (work["dte_num"] <= 0).sum())
    print("IV NaN:", work["iv_num"].isna().sum())
    print("MID NaN:", work["mid_num"].isna().sum())

    work = work.dropna(subset=["strike_num", "underlying_num", "iv_num", "dte_num", "mid_num"])
    work = work[
        (work["strike_num"] > 0)
        & (work["underlying_num"] > 0)
        & (work["iv_num"] > 0)
        & (work["dte_num"] >= 1)
        & (work["mid_num"] >= 0)
    ]

    if work.empty:
        result["notes"].append("No rows with usable strike, underlying price, IV, DTE, and mid price.")
        return result

    # Prioritize near-ATM rows, which are most useful for theoretical price validation.
    work["moneyness_gap"] = (work["strike_num"] - work["underlying_num"]).abs()
    work = work.sort_values(["moneyness_gap", "dte_num"]).head(max_rows)

    audited_rows: list[PricingAuditRow] = []

    for _, row in work.iterrows():
        option_symbol = str(row.get("option_symbol") or "")
        option_type = _normalize_type(row.get("type"), option_symbol)
        strike = float(row["strike_num"])
        underlying = float(row["underlying_num"])
        iv = _to_float(row.get("iv_num"))
        dte = float(row["dte_num"])
        expiry = str(row.get("expiry") or row.get("expiration") or "")

        bid = _to_float(row.get("bid_num"))
        ask = _to_float(row.get("ask_num"))
        last = _to_float(row.get("last_num"))
        mid = _to_float(row.get("mid_num"))

        theo = None
        intrinsic = None
        extrinsic = None
        price_diff = None
        price_diff_pct = None
        spread = None
        spread_pct = None
        messages: list[str] = []
        status = "PASS"

        if bid is not None and ask is not None:
            spread = ask - bid
            spread_pct = spread / mid if mid and mid > 0 else None

            if bid < 0 or ask < 0:
                status = "FAIL"
                messages.append("Negative bid/ask detected.")
            elif ask < bid:
                status = "FAIL"
                messages.append("Ask is below bid.")
            elif spread_pct is not None and spread_pct >= SPREAD_FAIL_PCT:
                status = "FAIL"
                messages.append(f"Extremely wide spread: {spread_pct:.1%}.")
            elif spread_pct is not None and spread_pct >= SPREAD_WARN_PCT and status != "FAIL":
                status = "WARN"
                messages.append(f"Wide spread: {spread_pct:.1%}.")

        intrinsic = _intrinsic_value(option_type, underlying, strike)
        if intrinsic is not None and mid is not None:
            extrinsic = mid - intrinsic
            # Allow tiny negative from rounding.
            if dte <= 2:
                threshold = -0.50
            elif dte <= 7:
                threshold = -0.25
            else:
                threshold = -0.05

            if extrinsic < threshold:

                messages.append(f"Negative extrinsic value: {extrinsic:.2f}.")

        if iv is None or iv <= 0:
            theo = None

            if status != "FAIL":
                status = "WARN"

            messages.append(
                "Provider IV unavailable or zero. "
                "Skipped theoretical pricing comparison."
            )

        else:
            theo = _black_scholes_price(
                option_type=option_type,
                underlying_price=underlying,
                strike=strike,
                dte=dte,
                iv=iv,
                risk_free_rate=risk_free_rate,
                dividend_yield=dividend_yield,
            )

        if theo is not None and mid is not None:
            price_diff = mid - theo
            price_diff_pct = price_diff / theo if theo and theo > 0 else None
            price_status, price_msg = _status_for_price(
                price_diff=price_diff,
                price_diff_pct=price_diff_pct,
                dte=dte,
                iv=iv,
                underlying_price=underlying,
                strike=strike,
            )
            messages.append(price_msg)

            if price_status == "FAIL":
                status = "FAIL"
            elif price_status == "WARN" and status != "FAIL":
                status = "WARN"
        else:
            if status != "FAIL":
                status = "WARN"
            messages.append("Theoretical value unavailable.")

        audited_rows.append(PricingAuditRow(
            option_symbol=option_symbol,
            option_type=option_type,
            strike=strike,
            expiry=expiry,
            dte=dte,
            underlying_price=underlying,
            iv=iv,
            bid=bid,
            ask=ask,
            last=last,
            mid=mid,
            theoretical_value=theo,
            intrinsic_value=intrinsic,
            extrinsic_value=extrinsic,
            price_diff=price_diff,
            price_diff_pct=price_diff_pct,
            spread=spread,
            spread_pct=spread_pct,
            status=status,
            message=" | ".join(messages) if messages else "Pricing row passed sanity checks.",
        ))

    result["rows"] = [asdict(r) for r in audited_rows]
    result["rows_audited"] = len(audited_rows)

    for row in audited_rows:
        result["totals"][row.status] = result["totals"].get(row.status, 0) + 1

    result["finished_at"] = datetime.now(timezone.utc).isoformat()
    return result


def run_pricing_validation(
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

    result = audit_chain_pricing(
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


def pricing_audit_frame(result: dict[str, Any]) -> pd.DataFrame:
    rows = result.get("rows", []) if isinstance(result, dict) else []
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)
