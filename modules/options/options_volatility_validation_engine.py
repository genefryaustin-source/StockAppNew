"""
modules/options/options_volatility_validation_engine.py

Read-only Options Volatility Validation Engine.

Validates option-chain implied volatility quality:
- IV availability and numeric sanity
- negative / zero / extreme IV detection
- call/put skew around matching strikes
- term structure across expirations
- smile continuity across strikes
- abrupt IV jumps
- missing IV clusters
- ATM IV sample quality

This module does NOT submit, cancel, modify orders, or write to the database.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

import pandas as pd


IV_EXTREME_LEVEL = 5.0          # 500% decimal IV
IV_ZERO_WARN_RATIO = 0.20       # warn if >20% rows have IV <= 0 / missing
SKEW_WARN_ABS = 0.25            # 25 vol points
SKEW_FAIL_ABS = 0.50            # 50 vol points
JUMP_WARN_ABS = 0.35            # 35 vol points adjacent strike jump
JUMP_FAIL_ABS = 0.75            # 75 vol points adjacent strike jump
TERM_WARN_ABS = 0.40            # 40 vol points ATM term jump
TERM_FAIL_ABS = 0.80            # 80 vol points ATM term jump


@dataclass
class VolatilityAuditCheck:
    category: str
    check: str
    status: str
    severity: str
    message: str
    details: dict[str, Any] | None = None


@dataclass
class VolatilitySurfaceRow:
    expiry: str
    option_type: str
    strike: float
    underlying_price: float | None
    iv: float | None
    dte: float | None
    option_symbol: str


def _ok(category: str, check: str, message: str, details: dict[str, Any] | None = None) -> VolatilityAuditCheck:
    return VolatilityAuditCheck(category, check, "PASS", "info", message, details or {})


def _warn(category: str, check: str, message: str, details: dict[str, Any] | None = None) -> VolatilityAuditCheck:
    return VolatilityAuditCheck(category, check, "WARN", "warning", message, details or {})


def _fail(category: str, check: str, message: str, details: dict[str, Any] | None = None) -> VolatilityAuditCheck:
    return VolatilityAuditCheck(category, check, "FAIL", "critical", message, details or {})


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


def _normalize_iv(value: Any) -> float | None:
    iv = _to_float(value)
    if iv is None:
        return None
    # Most app providers use decimal IV. This also handles percent-style 52.7.
    if iv > 10:
        return iv / 100.0
    return iv


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


def _prepare_surface_frame(chain_data: dict[str, Any]) -> pd.DataFrame:
    df = _extract_chain_frame(chain_data)
    if df.empty:
        return pd.DataFrame()

    if "option_symbol" not in df.columns:
        df["option_symbol"] = ""

    if "type" not in df.columns:
        df["type"] = ""

    if "expiry" not in df.columns and "expiration" in df.columns:
        df["expiry"] = df["expiration"]

    if "expiry" not in df.columns:
        df["expiry"] = ""

    for col in ["strike", "underlying_price", "dte", "iv"]:
        if col not in df.columns:
            df[col] = None

    out = pd.DataFrame({
        "expiry": df["expiry"].astype(str),
        "option_type": [
            _normalize_type(t, s)
            for t, s in zip(df["type"], df["option_symbol"])
        ],
        "strike": pd.to_numeric(df["strike"], errors="coerce"),
        "underlying_price": pd.to_numeric(df["underlying_price"], errors="coerce"),
        "dte": pd.to_numeric(df["dte"], errors="coerce"),
        "iv": df["iv"].apply(_normalize_iv),
        "option_symbol": df["option_symbol"].astype(str),
    })

    out = out.dropna(subset=["strike"])
    out = out[out["strike"] > 0]

    return out


def validate_iv_availability(surface: pd.DataFrame) -> list[VolatilityAuditCheck]:
    category = "IV Availability"
    checks: list[VolatilityAuditCheck] = []

    if surface.empty:
        return [_fail(category, "Rows", "No option rows available for volatility validation.")]

    total = len(surface)
    iv_present = surface["iv"].notna().sum()
    missing = total - iv_present
    missing_ratio = missing / total if total else 1.0

    if iv_present == 0:
        checks.append(_fail(category, "IV Presence", "No IV values are populated.", {
            "rows": int(total),
            "missing": int(missing),
        }))
    elif missing_ratio > IV_ZERO_WARN_RATIO:
        checks.append(_warn(category, "IV Presence", f"{missing_ratio:.1%} of rows are missing IV.", {
            "rows": int(total),
            "iv_present": int(iv_present),
            "missing": int(missing),
        }))
    else:
        checks.append(_ok(category, "IV Presence", f"{iv_present:,} of {total:,} rows have IV.", {
            "rows": int(total),
            "iv_present": int(iv_present),
            "missing": int(missing),
        }))

    usable = surface.dropna(subset=["iv"])
    if usable.empty:
        return checks

    negative = usable[usable["iv"] < 0]
    zero_or_tiny = usable[usable["iv"] <= 0.00001]
    extreme = usable[usable["iv"] >= IV_EXTREME_LEVEL]

    if not negative.empty:
        checks.append(_fail(category, "Negative IV", f"{len(negative)} negative IV value(s) found.", {
            "sample": negative[["option_symbol", "iv"]].head(10).to_dict("records"),
        }))
    else:
        checks.append(_ok(category, "Negative IV", "No negative IV values found."))

    zero_ratio = len(zero_or_tiny) / len(usable) if len(usable) else 0
    if zero_ratio > IV_ZERO_WARN_RATIO:
        checks.append(_warn(category, "Zero IV", f"{zero_ratio:.1%} of populated IV values are zero/tiny.", {
            "count": int(len(zero_or_tiny)),
        }))
    else:
        checks.append(_ok(category, "Zero IV", "Zero/tiny IV values are not excessive.", {
            "count": int(len(zero_or_tiny)),
        }))

    if not extreme.empty:
        checks.append(_warn(category, "Extreme IV", f"{len(extreme)} extreme IV value(s) found.", {
            "threshold": IV_EXTREME_LEVEL,
            "sample": extreme[["option_symbol", "strike", "iv", "dte"]].head(10).to_dict("records"),
        }))
    else:
        checks.append(_ok(category, "Extreme IV", "No extreme IV values above threshold."))

    checks.append(_ok(category, "IV Distribution", "IV distribution calculated.", {
        "min": float(usable["iv"].min()),
        "max": float(usable["iv"].max()),
        "mean": float(usable["iv"].mean()),
        "median": float(usable["iv"].median()),
    }))

    return checks


def validate_call_put_skew(surface: pd.DataFrame) -> list[VolatilityAuditCheck]:
    category = "Skew"
    checks: list[VolatilityAuditCheck] = []

    required = ["iv", "expiry", "strike"]

    missing = [
        c for c in required
        if c not in surface.columns
    ]

    if missing:
        return [
            _warn(
                category,
                "Call/Put Skew",
                f"Missing required columns: {missing}",
                {
                    "missing_columns": missing,
                },
            )
        ]
    print("=" * 80)
    print("CALL PUT SKEW COLUMNS")
    print("=" * 80)
    print(surface.columns.tolist())
    print("MISSING:", missing)
    print("=" * 80)
    usable = surface.dropna(
        subset=required
    )
    if usable.empty:
        return [_warn(category, "Call/Put Skew", "No usable IV rows for call/put skew validation.")]

    calls = usable[usable["option_type"] == "call"]
    puts = usable[usable["option_type"] == "put"]

    if calls.empty or puts.empty:
        return [_warn(category, "Call/Put Skew", "Both calls and puts are required for skew validation.", {
            "calls": int(len(calls)),
            "puts": int(len(puts)),
        })]

    merged = calls.merge(
        puts,
        on=["expiry", "strike"],
        suffixes=("_call", "_put"),
        how="inner",
    )

    if merged.empty:
        return [_warn(category, "Call/Put Skew", "No matching call/put strikes found.")]

    merged["skew_abs"] = (merged["iv_put"] - merged["iv_call"]).abs()
    max_skew = float(merged["skew_abs"].max())
    avg_skew = float(merged["skew_abs"].mean())

    severe = merged[merged["skew_abs"] >= SKEW_FAIL_ABS]
    moderate = merged[merged["skew_abs"] >= SKEW_WARN_ABS]

    if not severe.empty:
        checks.append(_fail(category, "Call/Put Skew", f"{len(severe)} matched strike(s) have severe call/put IV divergence.", {
            "max_skew": max_skew,
            "avg_skew": avg_skew,
            "sample": severe[["expiry", "strike", "iv_call", "iv_put", "skew_abs"]].head(10).to_dict("records"),
        }))
    elif not moderate.empty:
        checks.append(_warn(category, "Call/Put Skew", f"{len(moderate)} matched strike(s) have elevated call/put IV divergence.", {
            "max_skew": max_skew,
            "avg_skew": avg_skew,
            "sample": moderate[["expiry", "strike", "iv_call", "iv_put", "skew_abs"]].head(10).to_dict("records"),
        }))
    else:
        checks.append(_ok(category, "Call/Put Skew", "Call/put IV skew is within tolerance.", {
            "matched_rows": int(len(merged)),
            "max_skew": max_skew,
            "avg_skew": avg_skew,
        }))

    return checks


def validate_smile_continuity(surface: pd.DataFrame) -> list[VolatilityAuditCheck]:
    category = "Smile Continuity"
    checks: list[VolatilityAuditCheck] = []

    required = ["iv", "expiry", "strike"]

    missing = [
        c for c in required
        if c not in surface.columns
    ]

    if missing:
        return [
            _warn(
                category,
                "Adjacent Strike Jumps",
                f"Missing required columns: {missing}",
                {
                    "missing_columns": missing,
                },
            )
        ]

    usable = surface.dropna(
        subset=required
    )
    if usable.empty:
        return [_warn(category, "Adjacent Strike Jumps", "No usable IV rows for smile continuity validation.")]

    jump_records: list[dict[str, Any]] = []
    severe_records: list[dict[str, Any]] = []

    for (expiry, opt_type), group in usable.groupby(["expiry", "option_type"]):
        g = group.sort_values("strike").copy()
        if len(g) < 4:
            continue

        g["prev_strike"] = g["strike"].shift(1)
        g["prev_iv"] = g["iv"].shift(1)
        g["iv_jump"] = (g["iv"] - g["prev_iv"]).abs()
        jumps = g[g["iv_jump"] >= JUMP_WARN_ABS]

        if not jumps.empty:
            sample = jumps[["expiry", "option_type", "prev_strike", "strike", "prev_iv", "iv", "iv_jump"]].to_dict("records")
            jump_records.extend(sample)

        severe = g[g["iv_jump"] >= JUMP_FAIL_ABS]
        if not severe.empty:
            sample = severe[["expiry", "option_type", "prev_strike", "strike", "prev_iv", "iv", "iv_jump"]].to_dict("records")
            severe_records.extend(sample)

    if severe_records:
        checks.append(_fail(category, "Adjacent Strike Jumps", f"{len(severe_records)} severe adjacent IV jump(s) found.", {
            "sample": severe_records[:10],
        }))
    elif jump_records:
        checks.append(_warn(category, "Adjacent Strike Jumps", f"{len(jump_records)} elevated adjacent IV jump(s) found.", {
            "sample": jump_records[:10],
        }))
    else:
        checks.append(_ok(category, "Adjacent Strike Jumps", "No excessive adjacent-strike IV jumps found."))

    return checks


def validate_term_structure(surface: pd.DataFrame) -> list[VolatilityAuditCheck]:
    category = "Term Structure"
    checks: list[VolatilityAuditCheck] = []

    required = [
        "iv",
        "expiry",
        "strike",
        "dte",
        "underlying_price",
    ]

    missing = [
        c for c in required
        if c not in surface.columns
    ]

    if missing:
        return [
            _warn(
                category,
                "ATM Term Structure",
                f"Missing required columns: {missing}",
                {
                    "missing_columns": missing,
                },
            )
        ]

    usable = surface.dropna(
        subset=required
    )
    if usable.empty:
        return [_warn(category, "ATM Term Structure", "No usable rows for term structure validation.")]

    atm_rows: list[pd.Series] = []

    for (expiry, opt_type), group in usable.groupby(["expiry", "option_type"]):
        g = group.copy()
        if g.empty:
            continue
        g["moneyness_gap"] = (g["strike"] - g["underlying_price"]).abs()
        atm_rows.append(g.sort_values("moneyness_gap").iloc[0])

    if len(atm_rows) < 3:
        return [_warn(category, "ATM Term Structure", "Fewer than 3 expirations/sides available for term structure validation.", {
            "atm_points": len(atm_rows),
        })]

    atm = pd.DataFrame(atm_rows).sort_values(["option_type", "dte"])
    jump_records: list[dict[str, Any]] = []
    severe_records: list[dict[str, Any]] = []

    for opt_type, group in atm.groupby("option_type"):
        g = group.sort_values("dte").copy()
        g["prev_dte"] = g["dte"].shift(1)
        g["prev_iv"] = g["iv"].shift(1)
        g["term_jump"] = (g["iv"] - g["prev_iv"]).abs()

        jumps = g[g["term_jump"] >= TERM_WARN_ABS]
        if not jumps.empty:
            jump_records.extend(jumps[["option_type", "expiry", "dte", "iv", "prev_dte", "prev_iv", "term_jump"]].to_dict("records"))

        severe = g[g["term_jump"] >= TERM_FAIL_ABS]
        if not severe.empty:
            severe_records.extend(severe[["option_type", "expiry", "dte", "iv", "prev_dte", "prev_iv", "term_jump"]].to_dict("records"))

    if severe_records:
        checks.append(_fail(category, "ATM Term Structure", f"{len(severe_records)} severe ATM term-structure jump(s) found.", {
            "sample": severe_records[:10],
        }))
    elif jump_records:
        checks.append(_warn(category, "ATM Term Structure", f"{len(jump_records)} elevated ATM term-structure jump(s) found.", {
            "sample": jump_records[:10],
        }))
    else:
        checks.append(_ok(category, "ATM Term Structure", "ATM term structure changes are within tolerance.", {
            "atm_points": len(atm),
        }))

    return checks


def validate_atm_quality(surface: pd.DataFrame) -> list[VolatilityAuditCheck]:
    category = "ATM Quality"

    required = [
        "iv",
        "strike",
        "underlying_price",
    ]

    missing = [
        c for c in required
        if c not in surface.columns
    ]

    if missing:
        return [
            _warn(
                category,
                "ATM Sample",
                f"Missing required columns: {missing}",
                {
                    "missing_columns": missing,
                },
            )
        ]

    usable = surface.dropna(
        subset=required
    )
    if usable.empty:
        return [_warn(category, "ATM Sample", "No usable IV rows for ATM quality sample.")]

    rows: list[dict[str, Any]] = []
    for expiry, group in usable.groupby("expiry"):
        g = group.copy()
        g["moneyness_gap"] = (g["strike"] - g["underlying_price"]).abs()
        atm = g.sort_values("moneyness_gap").head(2)
        rows.extend(atm[["expiry", "option_type", "option_symbol", "strike", "underlying_price", "iv", "dte"]].to_dict("records"))

    return [_ok(category, "ATM Sample", "ATM IV sample generated for manual review.", {
        "sample": rows[:20],
    })]


def audit_chain_volatility(chain_data: dict[str, Any]) -> dict[str, Any]:
    surface = _prepare_surface_frame(chain_data)
    print("=" * 80)
    print("VOLATILITY SURFACE")
    print("=" * 80)
    print(type(surface))
    print(surface.columns.tolist() if hasattr(surface, "columns") else "NO COLUMNS")

    if isinstance(surface, pd.DataFrame) and not surface.empty:
        print(surface.head(3).to_dict("records"))

    print("=" * 80)

    checks: list[VolatilityAuditCheck] = []
    checks.extend(validate_iv_availability(surface))
    checks.extend(validate_call_put_skew(surface))
    checks.extend(validate_smile_continuity(surface))
    checks.extend(validate_term_structure(surface))
    checks.extend(validate_atm_quality(surface))

    totals = {
        "PASS": sum(1 for c in checks if c.status == "PASS"),
        "WARN": sum(1 for c in checks if c.status == "WARN"),
        "FAIL": sum(1 for c in checks if c.status == "FAIL"),
    }

    return {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "provider": chain_data.get("provider") if isinstance(chain_data, dict) else None,
        "source": chain_data.get("source") if isinstance(chain_data, dict) else None,
        "rows_available": int(len(surface)) if isinstance(surface, pd.DataFrame) else 0,
        "totals": totals,
        "checks": [asdict(c) for c in checks],
        "surface_sample": surface.head(100).to_dict("records") if isinstance(surface, pd.DataFrame) and not surface.empty else [],
    }


def run_volatility_validation(
    ticker: str = "SPY",
    expiration: str | None = None,
) -> dict[str, Any]:
    from modules.options.options_data_service import get_options_chain

    try:
        chain_data = get_options_chain(ticker, expiration=expiration)
    except TypeError:
        chain_data = get_options_chain(ticker)

    result = audit_chain_volatility(chain_data)
    result["ticker"] = ticker
    result["expiration"] = expiration
    return result


def volatility_audit_frame(result: dict[str, Any]) -> pd.DataFrame:
    rows = result.get("checks", []) if isinstance(result, dict) else []
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    if "details" in df.columns:
        df["details"] = df["details"].apply(lambda x: str(x)[:800])
    return df
