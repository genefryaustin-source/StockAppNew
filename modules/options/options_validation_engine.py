"""
modules/options/options_validation_engine.py

Read-only Options Validation & QA Engine.
Validates chain shape, Greeks sanity, IV sanity, portfolio positions, and order history.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

import math
import pandas as pd


@dataclass
class ValidationCheck:
    category: str
    check: str
    status: str
    severity: str
    message: str
    details: dict[str, Any] | None = None


def _ok(category: str, check: str, message: str, details: dict[str, Any] | None = None) -> ValidationCheck:
    return ValidationCheck(category, check, "PASS", "info", message, details or {})


def _warn(category: str, check: str, message: str, details: dict[str, Any] | None = None) -> ValidationCheck:
    return ValidationCheck(category, check, "WARN", "warning", message, details or {})


def _fail(category: str, check: str, message: str, details: dict[str, Any] | None = None) -> ValidationCheck:
    return ValidationCheck(category, check, "FAIL", "critical", message, details or {})


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


def validate_chain_shape(chain_data: dict[str, Any], ticker: str = "") -> list[ValidationCheck]:
    checks: list[ValidationCheck] = []
    category = "Chain"

    if not isinstance(chain_data, dict):
        return [_fail(category, "Payload", "Chain data is not a dictionary.")]

    provider = chain_data.get("provider") or chain_data.get("source") or "unknown"
    expirations = chain_data.get("expirations", []) or []
    df = _extract_chain_frame(chain_data)

    if chain_data.get("error"):
        checks.append(_warn(category, "Provider Error", f"Provider returned error: {chain_data.get('error')}", {
            "provider": provider,
            "error": chain_data.get("error"),
        }))

    if expirations:
        checks.append(_ok(category, "Expirations", f"{len(expirations)} expiration(s) returned.", {
            "provider": provider,
            "sample": list(expirations)[:10],
        }))
    else:
        checks.append(_fail(category, "Expirations", "No expirations returned.", {"provider": provider}))

    if df.empty:
        checks.append(_fail(category, "Rows", "No option rows returned.", {"provider": provider}))
        return checks

    checks.append(_ok(category, "Rows", f"{len(df):,} option row(s) returned.", {"provider": provider}))

    required = ["option_symbol", "strike"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        checks.append(_fail(category, "Required Columns", f"Missing required columns: {missing}", {
            "columns": list(df.columns),
        }))
    else:
        checks.append(_ok(category, "Required Columns", "Required contract columns are present."))

    if "type" in df.columns:
        types = set(str(v).lower() for v in df["type"].dropna().unique().tolist())
        if ("call" in types or "calls" in types) and ("put" in types or "puts" in types):
            checks.append(_ok(category, "Calls/Puts", "Both calls and puts are present.", {"types": sorted(types)}))
        else:
            checks.append(_warn(category, "Calls/Puts", "Only one option side appears present.", {"types": sorted(types)}))
    else:
        checks.append(_warn(category, "Calls/Puts", "No type column available to verify call/put coverage."))

    if "strike" in df.columns:
        strikes = pd.to_numeric(df["strike"], errors="coerce").dropna()
        if strikes.empty:
            checks.append(_fail(category, "Strike Values", "Strike column exists but has no numeric values."))
        else:
            checks.append(_ok(category, "Strike Values", f"Strike range {strikes.min():,.2f} to {strikes.max():,.2f}.", {
                "min": float(strikes.min()),
                "max": float(strikes.max()),
                "unique_count": int(strikes.nunique()),
            }))

    return checks


def validate_greeks(chain_data: dict[str, Any]) -> list[ValidationCheck]:
    checks: list[ValidationCheck] = []
    category = "Greeks"
    df = _extract_chain_frame(chain_data)

    if df.empty:
        return [_fail(category, "Availability", "No chain rows available for Greeks validation.")]

    greek_cols = ["delta", "gamma", "theta", "vega"]
    present = [c for c in greek_cols if c in df.columns]
    missing = [c for c in greek_cols if c not in df.columns]

    if missing:
        checks.append(_warn(category, "Columns", f"Missing Greeks columns: {missing}", {"present": present}))
    else:
        checks.append(_ok(category, "Columns", "Delta, gamma, theta, and vega columns are present."))

    if not present:
        return checks

    for col in present:
        vals = pd.to_numeric(df[col], errors="coerce").dropna()
        if vals.empty:
            checks.append(_warn(category, col.upper(), f"{col} column is present but empty."))
            continue

        if col == "delta":
            invalid = vals[(vals < -1.05) | (vals > 1.05)]
            if invalid.empty:
                checks.append(_ok(category, "Delta Range", "Delta values are within expected [-1, 1] range.", {
                    "min": float(vals.min()),
                    "max": float(vals.max()),
                }))
            else:
                checks.append(_fail(category, "Delta Range", f"{len(invalid)} delta value(s) outside expected range.", {
                    "min": float(vals.min()),
                    "max": float(vals.max()),
                }))

        elif col == "gamma":
            invalid = vals[vals < -0.0001]
            if invalid.empty:
                checks.append(_ok(category, "Gamma Range", "Gamma values are non-negative or near zero.", {
                    "min": float(vals.min()),
                    "max": float(vals.max()),
                }))
            else:
                checks.append(_warn(category, "Gamma Range", f"{len(invalid)} gamma value(s) are negative.", {
                    "min": float(vals.min()),
                    "max": float(vals.max()),
                }))

        elif col == "theta":
            checks.append(_ok(category, "Theta Presence", "Theta values are available.", {
                "min": float(vals.min()),
                "max": float(vals.max()),
                "negative_count": int((vals < 0).sum()),
                "positive_count": int((vals > 0).sum()),
            }))

        elif col == "vega":
            checks.append(_ok(category, "Vega Presence", "Vega values are available.", {
                "min": float(vals.min()),
                "max": float(vals.max()),
            }))

    if {"underlying_price", "strike", "delta"}.issubset(df.columns):
        tmp = df.copy()
        tmp["strike_num"] = pd.to_numeric(tmp["strike"], errors="coerce")
        tmp["underlying_num"] = pd.to_numeric(tmp["underlying_price"], errors="coerce")
        tmp["delta_num"] = pd.to_numeric(tmp["delta"], errors="coerce")
        tmp = tmp.dropna(subset=["strike_num", "underlying_num", "delta_num"])
        if not tmp.empty:
            tmp["moneyness_gap"] = (tmp["strike_num"] - tmp["underlying_num"]).abs()
            sample_cols = [c for c in ["option_symbol", "strike_num", "underlying_num", "delta_num"] if c in tmp.columns]
            atm = tmp.sort_values("moneyness_gap").head(10)
            checks.append(_ok(category, "ATM Delta Sample", "ATM sample extracted for manual review.", {
                "rows": atm[sample_cols].to_dict("records"),
            }))

    return checks


def validate_iv(chain_data: dict[str, Any]) -> list[ValidationCheck]:
    checks: list[ValidationCheck] = []
    category = "Volatility"
    df = _extract_chain_frame(chain_data)

    if df.empty:
        return [_fail(category, "Availability", "No chain rows available for IV validation.")]

    if "iv" not in df.columns:
        return [_warn(category, "IV Column", "No IV column found in chain rows.")]

    iv = pd.to_numeric(df["iv"], errors="coerce").dropna()
    if iv.empty:
        return [_warn(category, "IV Values", "IV column is present but empty.")]

    negative = iv[iv < 0]
    extreme = iv[iv > 10]

    if not negative.empty:
        checks.append(_fail(category, "IV Range", "Negative IV values found.", {
            "count": int(len(negative)),
            "min": float(iv.min()),
            "max": float(iv.max()),
        }))
    elif not extreme.empty:
        checks.append(_warn(category, "IV Range", "Very high IV values found; verify decimal vs percent normalization.", {
            "count": int(len(extreme)),
            "min": float(iv.min()),
            "max": float(iv.max()),
            "mean": float(iv.mean()),
        }))
    else:
        checks.append(_ok(category, "IV Range", "IV values appear numerically sane.", {
            "min": float(iv.min()),
            "max": float(iv.max()),
            "mean": float(iv.mean()),
        }))

    return checks


def validate_positions(paper: bool = True, ticker: str = "") -> list[ValidationCheck]:
    category = "Portfolio Positions"
    try:
        from modules.options.options_portfolio_engine import load_portfolio_positions, positions_frame
        positions = load_portfolio_positions(ticker=ticker, paper=paper)
        df = positions_frame(positions)
    except Exception as exc:
        return [_fail(category, "Load", f"Failed to load options positions: {exc}")]

    checks: list[ValidationCheck] = []

    if df.empty:
        checks.append(_ok(category, "Open Positions", "No open options positions found."))
        return checks

    checks.append(_ok(category, "Open Positions", f"{len(df)} open option position(s) found."))

    for col in ["qty", "market_value", "unrealized_pnl", "delta", "gamma", "theta", "vega"]:
        if col in df.columns:
            vals = pd.to_numeric(df[col], errors="coerce").fillna(0)
            checks.append(_ok(category, f"Aggregate {col}", f"Aggregate {col}: {vals.sum():,.4f}", {
                "sum": float(vals.sum()),
                "min": float(vals.min()),
                "max": float(vals.max()),
            }))

    return checks


def validate_orders(db: Any, tenant_id: str, limit: int = 50) -> list[ValidationCheck]:
    category = "Orders"
    try:
        from modules.options.options_models import ensure_tables, get_order_history
        ensure_tables(db)
        rows = get_order_history(db, tenant_id, limit=limit)
    except Exception as exc:
        return [_fail(category, "Load", f"Failed to load order history: {exc}")]

    checks: list[ValidationCheck] = []

    if not rows:
        return [_ok(category, "History", "No options orders found.")]

    df = pd.DataFrame(rows)
    checks.append(_ok(category, "History", f"{len(df)} order record(s) loaded."))

    if "status" in df.columns:
        status_counts = df["status"].fillna("unknown").value_counts().to_dict()
        checks.append(_ok(category, "Status Counts", "Order status distribution calculated.", status_counts))

        active_statuses = {"new", "accepted", "pending_new", "partially_filled", "held"}
        active_count = int(df["status"].astype(str).str.lower().isin(active_statuses).sum())
        if active_count:
            checks.append(_warn(category, "Active Orders", f"{active_count} active order(s) still working.", {
                "active_count": active_count,
            }))
        else:
            checks.append(_ok(category, "Active Orders", "No active working orders found."))

    if "error_msg" in df.columns:
        errors = df["error_msg"].dropna()
        errors = errors[errors.astype(str).str.strip().str.lower() != "none"]
        if len(errors):
            checks.append(_warn(category, "Errors", f"{len(errors)} order(s) contain error messages.", {
                "sample": errors.astype(str).head(5).tolist(),
            }))

    return checks


def run_options_validation(
    ticker: str = "SPY",
    expiration: str | None = None,
    paper: bool = True,
    db: Any | None = None,
    tenant_id: str = "tenant_default",
) -> dict[str, Any]:
    started_at = datetime.now(timezone.utc).isoformat()
    checks: list[ValidationCheck] = []
    chain_data: dict[str, Any] = {}

    try:
        from modules.options.options_data_service import get_options_chain
        try:
            chain_data = get_options_chain(ticker, expiration=expiration)
        except TypeError:
            chain_data = get_options_chain(ticker)

        checks.extend(validate_chain_shape(chain_data, ticker=ticker))
        checks.extend(validate_greeks(chain_data))
        checks.extend(validate_iv(chain_data))

    except Exception as exc:
        checks.append(_fail("Provider/Chain", "Load", f"Failed to load option chain: {exc}"))

    checks.extend(validate_positions(paper=paper, ticker=ticker))

    if db is not None:
        checks.extend(validate_orders(db, tenant_id=tenant_id))

    totals = {
        "PASS": sum(1 for c in checks if c.status == "PASS"),
        "WARN": sum(1 for c in checks if c.status == "WARN"),
        "FAIL": sum(1 for c in checks if c.status == "FAIL"),
    }

    return {
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "ticker": ticker,
        "expiration": expiration,
        "paper": paper,
        "provider": chain_data.get("provider") if isinstance(chain_data, dict) else None,
        "source": chain_data.get("source") if isinstance(chain_data, dict) else None,
        "totals": totals,
        "checks": [asdict(c) for c in checks],
    }


def validation_frame(result: dict[str, Any]) -> pd.DataFrame:
    rows = result.get("checks", []) if isinstance(result, dict) else []
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    if "details" in df.columns:
        df["details"] = df["details"].apply(lambda x: str(x)[:500])
    return df
