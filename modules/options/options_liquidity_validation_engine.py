"""
modules/options/options_liquidity_validation_engine.py

Read-only Options Liquidity Validation Engine.

Validates whether option contracts are practically tradable:
- Bid/ask availability
- Spread quality
- Open interest coverage
- Volume coverage
- Zero-bid contracts
- Wide-spread contracts
- Tradable contract percentage
- Liquidity by expiry
- Liquidity by option side
- ATM liquidity sample

This module does NOT submit, cancel, modify orders, or write to the database.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

import pandas as pd


SPREAD_WARN_PCT = 0.25
SPREAD_FAIL_PCT = 0.75

MIN_OPEN_INTEREST = 10
MIN_VOLUME = 1

TRADABLE_WARN_RATIO = 0.35
TRADABLE_FAIL_RATIO = 0.20

ZERO_BID_WARN_RATIO = 0.30
ZERO_BID_FAIL_RATIO = 0.60

WIDE_SPREAD_WARN_RATIO = 0.30
WIDE_SPREAD_FAIL_RATIO = 0.60


@dataclass
class LiquidityAuditCheck:
    category: str
    check: str
    status: str
    severity: str
    message: str
    details: dict[str, Any] | None = None


def _ok(category: str, check: str, message: str, details: dict[str, Any] | None = None) -> LiquidityAuditCheck:
    return LiquidityAuditCheck(category, check, "PASS", "info", message, details or {})


def _warn(category: str, check: str, message: str, details: dict[str, Any] | None = None) -> LiquidityAuditCheck:
    return LiquidityAuditCheck(category, check, "WARN", "warning", message, details or {})


def _fail(category: str, check: str, message: str, details: dict[str, Any] | None = None) -> LiquidityAuditCheck:
    return LiquidityAuditCheck(category, check, "FAIL", "critical", message, details or {})


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


def _prepare_liquidity_frame(chain_data: dict[str, Any]) -> pd.DataFrame:
    df = _extract_chain_frame(chain_data)
    if df.empty:
        return pd.DataFrame()

    df = df.copy()

    if "option_symbol" not in df.columns:
        df["option_symbol"] = ""

    if "type" not in df.columns:
        df["type"] = ""

    if "expiry" not in df.columns and "expiration" in df.columns:
        df["expiry"] = df["expiration"]

    if "expiry" not in df.columns:
        df["expiry"] = ""

    defaults = {
        "strike": None,
        "bid": None,
        "ask": None,
        "mid": None,
        "last": None,
        "volume": 0,
        "open_interest": 0,
        "dte": None,
        "underlying_price": None,
    }

    for col, default in defaults.items():
        if col not in df.columns:
            df[col] = default

    out = pd.DataFrame({
        "option_symbol": df["option_symbol"].astype(str),
        "expiry": df["expiry"].astype(str),
        "option_type": [_normalize_type(t, s) for t, s in zip(df["type"], df["option_symbol"])],
        "strike": pd.to_numeric(df["strike"], errors="coerce"),
        "bid": pd.to_numeric(df["bid"], errors="coerce"),
        "ask": pd.to_numeric(df["ask"], errors="coerce"),
        "mid": pd.to_numeric(df["mid"], errors="coerce"),
        "last": pd.to_numeric(df["last"], errors="coerce"),
        "volume": pd.to_numeric(df["volume"], errors="coerce").fillna(0),
        "open_interest": pd.to_numeric(df["open_interest"], errors="coerce").fillna(0),
        "dte": pd.to_numeric(df["dte"], errors="coerce"),
        "underlying_price": pd.to_numeric(df["underlying_price"], errors="coerce"),
    })

    missing_mid = out["mid"].isna() & out["bid"].notna() & out["ask"].notna()
    out.loc[missing_mid, "mid"] = (out.loc[missing_mid, "bid"] + out.loc[missing_mid, "ask"]) / 2.0

    out["spread"] = out["ask"] - out["bid"]
    out["spread"] = out["spread"].where((out["bid"] >= 0) & (out["ask"] >= 0), pd.NA)

    out["spread_pct"] = out["spread"] / out["mid"].replace(0, pd.NA)

    out["has_quote"] = (
        out["bid"].notna()
        & out["ask"].notna()
        & (out["ask"] >= out["bid"])
        & (out["ask"] > 0)
    )

    out["zero_bid"] = out["bid"].fillna(0) <= 0

    out["wide_spread"] = (
        out["spread_pct"].notna()
        & (out["spread_pct"] >= SPREAD_WARN_PCT)
    )

    out["severe_spread"] = (
        out["spread_pct"].notna()
        & (out["spread_pct"] >= SPREAD_FAIL_PCT)
    )

    out["has_open_interest"] = out["open_interest"] >= MIN_OPEN_INTEREST
    out["has_volume"] = out["volume"] >= MIN_VOLUME

    out["tradable"] = (
        out["has_quote"]
        & ~out["zero_bid"]
        & ~out["severe_spread"]
        & (out["has_open_interest"] | out["has_volume"])
    )

    out = out.dropna(subset=["strike"])
    out = out[out["strike"] > 0]

    return out.reset_index(drop=True)


def validate_quote_coverage(df: pd.DataFrame) -> list[LiquidityAuditCheck]:
    category = "Quote Quality"

    if df.empty:
        return [_fail(category, "Rows", "No option rows available for liquidity validation.")]

    total = len(df)
    quote_count = int(df["has_quote"].sum())
    quote_ratio = quote_count / total if total else 0

    if quote_ratio < 0.50:
        return [_fail(category, "Quote Coverage", f"Only {quote_ratio:.1%} of contracts have usable bid/ask quotes.", {
            "rows": total,
            "quoted": quote_count,
        })]

    if quote_ratio < 0.80:
        return [_warn(category, "Quote Coverage", f"{quote_ratio:.1%} of contracts have usable bid/ask quotes.", {
            "rows": total,
            "quoted": quote_count,
        })]

    return [_ok(category, "Quote Coverage", f"{quote_ratio:.1%} of contracts have usable bid/ask quotes.", {
        "rows": total,
        "quoted": quote_count,
    })]


def validate_zero_bids(df: pd.DataFrame) -> list[LiquidityAuditCheck]:
    category = "Quote Quality"

    if df.empty:
        return [_fail(category, "Zero Bids", "No option rows available.")]

    total = len(df)
    zero_count = int(df["zero_bid"].sum())
    ratio = zero_count / total if total else 0

    if ratio >= ZERO_BID_FAIL_RATIO:
        return [_fail(category, "Zero Bids", f"{ratio:.1%} of contracts have zero or missing bid.", {
            "zero_bid_count": zero_count,
            "rows": total,
        })]

    if ratio >= ZERO_BID_WARN_RATIO:
        return [_warn(category, "Zero Bids", f"{ratio:.1%} of contracts have zero or missing bid.", {
            "zero_bid_count": zero_count,
            "rows": total,
        })]

    return [_ok(category, "Zero Bids", "Zero-bid contracts are not excessive.", {
        "zero_bid_count": zero_count,
        "rows": total,
    })]


def validate_spreads(df: pd.DataFrame) -> list[LiquidityAuditCheck]:
    category = "Spread Quality"

    if df.empty:
        return [_fail(category, "Spreads", "No option rows available.")]

    usable = df[df["spread_pct"].notna()].copy()
    if usable.empty:
        return [_fail(category, "Spreads", "No usable spread data available.")]

    wide = usable[usable["wide_spread"]]
    severe = usable[usable["severe_spread"]]

    wide_ratio = len(wide) / len(usable) if len(usable) else 0
    severe_ratio = len(severe) / len(usable) if len(usable) else 0

    checks: list[LiquidityAuditCheck] = []

    if severe_ratio >= WIDE_SPREAD_FAIL_RATIO:
        checks.append(_fail(category, "Severe Spreads", f"{severe_ratio:.1%} of quoted contracts have severe spreads.", {
            "severe_count": int(len(severe)),
            "quoted_rows": int(len(usable)),
            "sample": severe[["option_symbol", "bid", "ask", "mid", "spread", "spread_pct"]].head(10).to_dict("records"),
        }))
    elif severe_ratio > 0:
        checks.append(_warn(category, "Severe Spreads", f"{severe_ratio:.1%} of quoted contracts have severe spreads.", {
            "severe_count": int(len(severe)),
            "quoted_rows": int(len(usable)),
            "sample": severe[["option_symbol", "bid", "ask", "mid", "spread", "spread_pct"]].head(10).to_dict("records"),
        }))
    else:
        checks.append(_ok(category, "Severe Spreads", "No severe spreads detected."))

    if wide_ratio >= WIDE_SPREAD_FAIL_RATIO:
        checks.append(_fail(category, "Wide Spreads", f"{wide_ratio:.1%} of quoted contracts have wide spreads.", {
            "wide_count": int(len(wide)),
            "quoted_rows": int(len(usable)),
        }))
    elif wide_ratio >= WIDE_SPREAD_WARN_RATIO:
        checks.append(_warn(category, "Wide Spreads", f"{wide_ratio:.1%} of quoted contracts have wide spreads.", {
            "wide_count": int(len(wide)),
            "quoted_rows": int(len(usable)),
        }))
    else:
        checks.append(_ok(category, "Wide Spreads", "Wide-spread contracts are not excessive.", {
            "wide_count": int(len(wide)),
            "quoted_rows": int(len(usable)),
        }))

    checks.append(_ok(category, "Spread Distribution", "Spread distribution calculated.", {
        "avg_spread_pct": float(usable["spread_pct"].mean()),
        "median_spread_pct": float(usable["spread_pct"].median()),
        "max_spread_pct": float(usable["spread_pct"].max()),
        "avg_spread": float(usable["spread"].mean()),
        "median_spread": float(usable["spread"].median()),
    }))

    return checks


def validate_volume_open_interest(df: pd.DataFrame) -> list[LiquidityAuditCheck]:
    category = "Depth"

    if df.empty:
        return [_fail(category, "Volume/OI", "No option rows available.")]

    total = len(df)
    oi_count = int((df["open_interest"] >= MIN_OPEN_INTEREST).sum())
    vol_count = int((df["volume"] >= MIN_VOLUME).sum())
    either_count = int(((df["open_interest"] >= MIN_OPEN_INTEREST) | (df["volume"] >= MIN_VOLUME)).sum())

    either_ratio = either_count / total if total else 0

    checks: list[LiquidityAuditCheck] = []

    if either_ratio < 0.25:
        checks.append(_fail(category, "Volume/OI Coverage", f"Only {either_ratio:.1%} of contracts have meaningful volume or open interest.", {
            "rows": total,
            "oi_count": oi_count,
            "volume_count": vol_count,
            "either_count": either_count,
        }))
    elif either_ratio < 0.50:
        checks.append(_warn(category, "Volume/OI Coverage", f"{either_ratio:.1%} of contracts have meaningful volume or open interest.", {
            "rows": total,
            "oi_count": oi_count,
            "volume_count": vol_count,
            "either_count": either_count,
        }))
    else:
        checks.append(_ok(category, "Volume/OI Coverage", f"{either_ratio:.1%} of contracts have meaningful volume or open interest.", {
            "rows": total,
            "oi_count": oi_count,
            "volume_count": vol_count,
            "either_count": either_count,
        }))

    checks.append(_ok(category, "Depth Distribution", "Volume and open interest distribution calculated.", {
        "total_volume": float(df["volume"].sum()),
        "avg_volume": float(df["volume"].mean()),
        "max_volume": float(df["volume"].max()),
        "total_open_interest": float(df["open_interest"].sum()),
        "avg_open_interest": float(df["open_interest"].mean()),
        "max_open_interest": float(df["open_interest"].max()),
    }))

    return checks


def validate_tradable_contracts(df: pd.DataFrame) -> list[LiquidityAuditCheck]:
    category = "Tradability"

    if df.empty:
        return [_fail(category, "Tradable Contracts", "No option rows available.")]

    total = len(df)
    tradable_count = int(df["tradable"].sum())
    ratio = tradable_count / total if total else 0

    if ratio < TRADABLE_FAIL_RATIO:
        return [_fail(category, "Tradable Contracts", f"Only {ratio:.1%} of contracts meet tradability criteria.", {
            "rows": total,
            "tradable": tradable_count,
            "criteria": "quote + nonzero bid + not severe spread + volume or open interest",
        })]

    if ratio < TRADABLE_WARN_RATIO:
        return [_warn(category, "Tradable Contracts", f"{ratio:.1%} of contracts meet tradability criteria.", {
            "rows": total,
            "tradable": tradable_count,
            "criteria": "quote + nonzero bid + not severe spread + volume or open interest",
        })]

    return [_ok(category, "Tradable Contracts", f"{ratio:.1%} of contracts meet tradability criteria.", {
        "rows": total,
        "tradable": tradable_count,
        "criteria": "quote + nonzero bid + not severe spread + volume or open interest",
    })]


def liquidity_grade(totals: dict[str, int]) -> str:
    fail = int(totals.get("FAIL", 0))
    warn = int(totals.get("WARN", 0))

    if fail >= 3:
        return "D"
    if fail >= 1:
        return "C"
    if warn >= 3:
        return "B"
    if warn >= 1:
        return "A-"
    return "A"


def liquidity_summary_tables(df: pd.DataFrame) -> dict[str, list[dict[str, Any]]]:
    if df.empty:
        return {
            "by_expiry": [],
            "by_side": [],
            "atm_sample": [],
        }

    working = df.copy()

    by_expiry = (
        working.groupby("expiry", as_index=False)
        .agg(
            contracts=("option_symbol", "count"),
            tradable=("tradable", "sum"),
            avg_spread_pct=("spread_pct", "mean"),
            total_volume=("volume", "sum"),
            total_open_interest=("open_interest", "sum"),
        )
    )
    by_expiry["tradable_pct"] = (
        by_expiry["tradable"] / by_expiry["contracts"].replace(0, 1) * 100
    ).round(2)

    by_side = (
        working.groupby("option_type", as_index=False)
        .agg(
            contracts=("option_symbol", "count"),
            tradable=("tradable", "sum"),
            avg_spread_pct=("spread_pct", "mean"),
            total_volume=("volume", "sum"),
            total_open_interest=("open_interest", "sum"),
        )
    )
    by_side["tradable_pct"] = (
        by_side["tradable"] / by_side["contracts"].replace(0, 1) * 100
    ).round(2)

    atm_sample: list[dict[str, Any]] = []
    atm_work = working.dropna(subset=["underlying_price", "strike"])
    if not atm_work.empty:
        for expiry, group in atm_work.groupby("expiry"):
            g = group.copy()
            g["moneyness_gap"] = (g["strike"] - g["underlying_price"]).abs()
            sample = g.sort_values(["moneyness_gap", "option_type"]).head(10)
            atm_sample.extend(
                sample[
                    [
                        "option_symbol",
                        "expiry",
                        "option_type",
                        "strike",
                        "underlying_price",
                        "bid",
                        "ask",
                        "mid",
                        "spread_pct",
                        "volume",
                        "open_interest",
                        "tradable",
                    ]
                ].to_dict("records")
            )

    for table in [by_expiry, by_side]:
        for col in ["avg_spread_pct"]:
            if col in table.columns:
                table[col] = pd.to_numeric(table[col], errors="coerce").fillna(0).round(4)

    return {
        "by_expiry": by_expiry.to_dict("records"),
        "by_side": by_side.to_dict("records"),
        "atm_sample": atm_sample[:50],
    }


def audit_chain_liquidity(chain_data: dict[str, Any]) -> dict[str, Any]:
    df = _prepare_liquidity_frame(chain_data)

    checks: list[LiquidityAuditCheck] = []
    checks.extend(validate_quote_coverage(df))
    checks.extend(validate_zero_bids(df))
    checks.extend(validate_spreads(df))
    checks.extend(validate_volume_open_interest(df))
    checks.extend(validate_tradable_contracts(df))

    totals = {
        "PASS": sum(1 for c in checks if c.status == "PASS"),
        "WARN": sum(1 for c in checks if c.status == "WARN"),
        "FAIL": sum(1 for c in checks if c.status == "FAIL"),
    }

    summary_tables = liquidity_summary_tables(df)

    return {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "provider": chain_data.get("provider") if isinstance(chain_data, dict) else None,
        "source": chain_data.get("source") if isinstance(chain_data, dict) else None,
        "rows_available": int(len(df)) if isinstance(df, pd.DataFrame) else 0,
        "grade": liquidity_grade(totals),
        "totals": totals,
        "checks": [asdict(c) for c in checks],
        "by_expiry": summary_tables["by_expiry"],
        "by_side": summary_tables["by_side"],
        "atm_sample": summary_tables["atm_sample"],
        "liquidity_sample": (
            df.head(100).to_dict("records")
            if isinstance(df, pd.DataFrame) and not df.empty
            else []
        ),
    }


def run_liquidity_validation(
    ticker: str = "SPY",
    expiration: str | None = None,
) -> dict[str, Any]:
    from modules.options.options_data_service import get_options_chain

    try:
        chain_data = get_options_chain(ticker, expiration=expiration)
    except TypeError:
        chain_data = get_options_chain(ticker)

    result = audit_chain_liquidity(chain_data)
    result["ticker"] = ticker
    result["expiration"] = expiration

    return result


def liquidity_audit_frame(result: dict[str, Any]) -> pd.DataFrame:
    rows = result.get("checks", []) if isinstance(result, dict) else []
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    if "details" in df.columns:
        df["details"] = df["details"].apply(lambda x: str(x)[:1000])

    return df
