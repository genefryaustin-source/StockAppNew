"""
modules/providers/provider_validation_engine.py

Read-only Provider Validation Engine.

Validates provider telemetry, market-data cache, price-history feed, and failover readiness.
This module does not call external APIs, consume provider limits, or write to the database.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

import pandas as pd
from sqlalchemy import text


@dataclass
class ProviderValidationCheck:
    category: str
    check: str
    status: str
    severity: str
    message: str
    details: dict[str, Any] | None = None


def _ok(category: str, check: str, message: str, details: dict[str, Any] | None = None) -> ProviderValidationCheck:
    return ProviderValidationCheck(category, check, "PASS", "info", message, details or {})


def _warn(category: str, check: str, message: str, details: dict[str, Any] | None = None) -> ProviderValidationCheck:
    return ProviderValidationCheck(category, check, "WARN", "warning", message, details or {})


def _fail(category: str, check: str, message: str, details: dict[str, Any] | None = None) -> ProviderValidationCheck:
    return ProviderValidationCheck(category, check, "FAIL", "critical", message, details or {})


def _safe_execute(db: Any, sql: str, params: dict[str, Any] | None = None):
    return db.execute(text(sql), params or {})


def _table_exists(db: Any, table_name: str) -> bool:
    try:
        row = _safe_execute(
            db,
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = :table_name
            ) AS exists_flag
            """,
            {"table_name": table_name},
        ).mappings().first()
        if row is not None:
            return bool(row.get("exists_flag"))
    except Exception:
        pass

    try:
        _safe_execute(db, f"SELECT 1 FROM {table_name} LIMIT 1")
        return True
    except Exception:
        return False


def _columns(db: Any, table_name: str) -> set[str]:
    try:
        rows = _safe_execute(
            db,
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = :table_name
            """,
            {"table_name": table_name},
        ).mappings().all()
        return {str(r.get("column_name")) for r in rows}
    except Exception:
        return set()


def _count_rows(db: Any, table_name: str) -> int:
    if not _table_exists(db, table_name):
        return 0
    try:
        row = _safe_execute(db, f"SELECT COUNT(*) AS n FROM {table_name}").mappings().first()
        return int(row.get("n", 0)) if row else 0
    except Exception:
        return 0


def _first_col(cols: set[str], candidates: list[str]) -> str | None:
    return next((c for c in candidates if c in cols), None)


def _age_days(value: Any) -> float | None:
    try:
        ts = pd.to_datetime(value, errors="coerce", utc=True)
        if pd.isna(ts):
            return None
        now = pd.Timestamp.now(tz="UTC")
        return float((now - ts).total_seconds() / 86400.0)
    except Exception:
        return None


def _score_from_counts(pass_count: int, warn_count: int, fail_count: int) -> float:
    total = pass_count + warn_count + fail_count
    if total <= 0:
        return 0.0
    return round(((pass_count + warn_count * 0.5) / total) * 100.0, 2)


def _status_from_counts(pass_count: int, warn_count: int, fail_count: int) -> str:
    if fail_count:
        return "FAIL"
    if warn_count:
        return "WARN"
    return "PASS"


def validate_provider_telemetry(db: Any) -> list[ProviderValidationCheck]:
    category = "Provider Telemetry"
    table = "provider_telemetry"
    checks: list[ProviderValidationCheck] = []

    if not _table_exists(db, table):
        return [_warn(category, "Table", "provider_telemetry table not found.")]

    cols = _columns(db, table)
    total = _count_rows(db, table)

    if total <= 0:
        return [_warn(category, "Rows", "provider_telemetry exists but contains no rows.")]

    checks.append(_ok(category, "Rows", f"provider_telemetry contains {total:,} row(s).", {"rows": total}))

    provider_col = _first_col(cols, ["provider", "provider_name", "name"])
    captured_col = _first_col(cols, ["captured_at", "created_at", "updated_at", "asof", "timestamp"])
    health_col = _first_col(cols, ["health_score", "score", "provider_score"])
    failure_col = _first_col(cols, ["failure_count", "fail_count", "errors", "error_count"])
    rate_col = _first_col(cols, ["rate_limit_count", "rate_limits", "rate_limited_count"])
    latency_col = _first_col(cols, ["avg_latency_ms", "latency_ms", "average_latency_ms"])

    if not provider_col:
        checks.append(_warn(category, "Provider Column", "No recognized provider name column found.", {"columns": sorted(cols)}))
        return checks

    select_cols = [provider_col]
    for col in [captured_col, health_col, failure_col, rate_col, latency_col]:
        if col and col not in select_cols:
            select_cols.append(col)

    order_col = captured_col or provider_col

    try:
        rows = _safe_execute(
            db,
            f"SELECT {', '.join(select_cols)} FROM {table} ORDER BY {order_col} DESC LIMIT 1000",
        ).mappings().all()
        df = pd.DataFrame(rows)
    except Exception as exc:
        return [_fail(category, "Query", f"Failed to query provider telemetry: {exc}")]

    if df.empty:
        return [_warn(category, "Rows", "No provider telemetry rows returned.")]

    providers = sorted(df[provider_col].dropna().astype(str).str.lower().unique().tolist())
    checks.append(_ok(category, "Provider Coverage", f"{len(providers)} provider(s) represented in telemetry.", {"providers": providers}))

    if captured_col:
        latest = df[captured_col].dropna().max() if captured_col in df.columns else None
        age = _age_days(latest)
        if age is None:
            checks.append(_warn(category, "Freshness", "Could not determine provider telemetry freshness.", {"column": captured_col}))
        elif age <= 1:
            checks.append(_ok(category, "Freshness", f"Provider telemetry is fresh: {age:.2f} day(s) old.", {"latest": str(latest)}))
        elif age <= 7:
            checks.append(_warn(category, "Freshness", f"Provider telemetry is {age:.2f} day(s) old.", {"latest": str(latest)}))
        else:
            checks.append(_fail(category, "Freshness", f"Provider telemetry is stale: {age:.2f} day(s) old.", {"latest": str(latest)}))
    else:
        checks.append(_warn(category, "Freshness", "No timestamp column found for provider telemetry."))

    if health_col and health_col in df.columns:
        health = pd.to_numeric(df[health_col], errors="coerce")
        bad = health.notna() & ((health < 0) | (health > 100))
        low = health.notna() & (health < 50)
        if bad.any():
            checks.append(_fail(category, "Health Score", f"{int(bad.sum())} row(s) have health score outside 0-100.", {"column": health_col}))
        elif low.any():
            checks.append(_warn(category, "Health Score", f"{int(low.sum())} row(s) show health score below 50.", {"column": health_col}))
        else:
            checks.append(_ok(category, "Health Score", "Provider health scores appear valid.", {"column": health_col}))
    else:
        checks.append(_warn(category, "Health Score", "No health score column found in telemetry."))

    if failure_col and failure_col in df.columns:
        failures = pd.to_numeric(df[failure_col], errors="coerce").fillna(0)
        if failures.sum() > 0:
            checks.append(_warn(category, "Failures", f"Telemetry reports {int(failures.sum())} provider failure(s).", {"column": failure_col}))
        else:
            checks.append(_ok(category, "Failures", "No provider failures reported in sampled telemetry.", {"column": failure_col}))

    if rate_col and rate_col in df.columns:
        rate_limits = pd.to_numeric(df[rate_col], errors="coerce").fillna(0)
        if rate_limits.sum() > 0:
            checks.append(_warn(category, "Rate Limits", f"Telemetry reports {int(rate_limits.sum())} rate-limit event(s).", {"column": rate_col}))
        else:
            checks.append(_ok(category, "Rate Limits", "No rate-limit events reported in sampled telemetry.", {"column": rate_col}))

    if latency_col and latency_col in df.columns:
        latency = pd.to_numeric(df[latency_col], errors="coerce")
        avg_latency = float(latency.dropna().mean()) if latency.notna().any() else None
        if avg_latency is None:
            checks.append(_warn(category, "Latency", "Latency column exists but has no usable values.", {"column": latency_col}))
        elif avg_latency <= 2000:
            checks.append(_ok(category, "Latency", f"Average provider latency is {avg_latency:.0f} ms.", {"column": latency_col}))
        elif avg_latency <= 5000:
            checks.append(_warn(category, "Latency", f"Average provider latency is elevated: {avg_latency:.0f} ms.", {"column": latency_col}))
        else:
            checks.append(_fail(category, "Latency", f"Average provider latency is high: {avg_latency:.0f} ms.", {"column": latency_col}))

    return checks


def validate_market_data_cache(db: Any) -> list[ProviderValidationCheck]:
    category = "Market Data Cache"
    table = "market_data_cache"
    checks: list[ProviderValidationCheck] = []

    if not _table_exists(db, table):
        return [_warn(category, "Table", "market_data_cache table not found.")]

    cols = _columns(db, table)
    total = _count_rows(db, table)

    if total <= 0:
        return [_warn(category, "Rows", "market_data_cache exists but contains no rows.")]

    checks.append(_ok(category, "Rows", f"market_data_cache contains {total:,} row(s).", {"rows": total}))

    symbol_col = _first_col(cols, ["symbol", "ticker"])
    provider_col = _first_col(cols, ["provider", "source", "provider_name"])
    time_col = _first_col(cols, ["created_at", "updated_at", "captured_at", "asof", "timestamp"])
    price_col = _first_col(cols, ["price", "close", "last_price", "current_price", "latest_price"])

    if symbol_col:
        try:
            row = _safe_execute(db, f"SELECT COUNT(DISTINCT {symbol_col}) AS n FROM {table}").mappings().first()
            n = int(row.get("n", 0)) if row else 0
            checks.append(_ok(category, "Symbol Coverage", f"{n:,} distinct symbol(s) in market data cache.", {"symbol_col": symbol_col}))
        except Exception as exc:
            checks.append(_warn(category, "Symbol Coverage", f"Could not validate symbol coverage: {exc}"))
    else:
        checks.append(_warn(category, "Symbol Coverage", "No symbol column found in market_data_cache."))

    if provider_col:
        try:
            rows = _safe_execute(
                db,
                f"SELECT {provider_col} AS provider, COUNT(*) AS rows FROM {table} GROUP BY {provider_col} ORDER BY rows DESC",
            ).mappings().all()
            checks.append(_ok(category, "Provider Coverage", "Provider distribution calculated.", {"providers": [dict(r) for r in rows[:20]]}))
        except Exception as exc:
            checks.append(_warn(category, "Provider Coverage", f"Could not validate provider distribution: {exc}"))
    else:
        checks.append(_warn(category, "Provider Coverage", "No provider/source column found in market_data_cache."))

    if price_col:
        try:
            rows = _safe_execute(db, f"SELECT {price_col} AS price FROM {table} LIMIT 5000").mappings().all()
            df = pd.DataFrame(rows)
            prices = pd.to_numeric(df["price"], errors="coerce")
            bad = prices.isna() | (prices <= 0)
            if bad.any():
                checks.append(_warn(category, "Price Values", f"{int(bad.sum())} sampled cache price row(s) are missing/non-positive.", {"column": price_col}))
            else:
                checks.append(_ok(category, "Price Values", "Sampled cache price values are positive.", {"column": price_col}))
        except Exception as exc:
            checks.append(_warn(category, "Price Values", f"Could not validate cache prices: {exc}"))
    else:
        checks.append(_warn(category, "Price Values", "No recognized price column found in market_data_cache."))

    if time_col:
        try:
            row = _safe_execute(db, f"SELECT MAX({time_col}) AS max_time FROM {table}").mappings().first()
            max_time = row.get("max_time") if row else None
            age = _age_days(max_time)
            if age is None:
                checks.append(_warn(category, "Freshness", "Could not determine market data cache freshness.", {"column": time_col}))
            elif age <= 1:
                checks.append(_ok(category, "Freshness", f"Market data cache is fresh: {age:.2f} day(s) old.", {"latest": str(max_time)}))
            elif age <= 7:
                checks.append(_warn(category, "Freshness", f"Market data cache is {age:.2f} day(s) old.", {"latest": str(max_time)}))
            else:
                checks.append(_fail(category, "Freshness", f"Market data cache is stale: {age:.2f} day(s) old.", {"latest": str(max_time)}))
        except Exception as exc:
            checks.append(_warn(category, "Freshness", f"Could not validate cache freshness: {exc}"))
    else:
        checks.append(_warn(category, "Freshness", "No timestamp column found in market_data_cache."))

    return checks


def validate_price_history_feed(db: Any) -> list[ProviderValidationCheck]:
    category = "Price History Feed"
    table = "price_history"
    checks: list[ProviderValidationCheck] = []

    if not _table_exists(db, table):
        return [_warn(category, "Table", "price_history table not found.")]

    cols = _columns(db, table)
    total = _count_rows(db, table)

    if total <= 0:
        return [_warn(category, "Rows", "price_history exists but contains no rows.")]

    checks.append(_ok(category, "Rows", f"price_history contains {total:,} row(s).", {"rows": total}))

    required = ["symbol", "date", "open", "high", "low", "close", "volume"]
    missing = [c for c in required if c not in cols]
    if missing:
        return [_fail(category, "Schema", f"price_history missing required OHLCV columns: {missing}", {"columns": sorted(cols)})]

    try:
        latest_row = _safe_execute(db, "SELECT MAX(date) AS latest_date FROM price_history").mappings().first()
        latest_date = latest_row.get("latest_date") if latest_row else None
        age = _age_days(latest_date)
        if age is None:
            checks.append(_warn(category, "Freshness", "Could not determine price_history freshness."))
        elif age <= 5:
            checks.append(_ok(category, "Freshness", f"price_history latest date is {age:.1f} day(s) old.", {"latest": str(latest_date)}))
        elif age <= 30:
            checks.append(_warn(category, "Freshness", f"price_history latest date is {age:.1f} day(s) old.", {"latest": str(latest_date)}))
        else:
            checks.append(_fail(category, "Freshness", f"price_history is stale: {age:.1f} day(s) old.", {"latest": str(latest_date)}))
    except Exception as exc:
        checks.append(_warn(category, "Freshness", f"Could not validate price_history freshness: {exc}"))

    try:
        row = _safe_execute(
            db,
            """
            SELECT
                COUNT(*) AS total_rows,
                SUM(
                    CASE
                        WHEN high < low
                          OR high < open
                          OR low > open
                          OR open <= 0
                          OR high <= 0
                          OR low <= 0
                          OR close <= 0
                          OR volume < 0
                        THEN 1 ELSE 0
                    END
                ) AS invalid_rows
            FROM price_history
            """,
        ).mappings().first()

        total_rows = int(row.get("total_rows") or 0)
        invalid_rows = int(row.get("invalid_rows") or 0)
        invalid_pct = invalid_rows / total_rows if total_rows else 0.0

        if invalid_rows == 0:
            checks.append(_ok(category, "OHLCV Integrity", f"Validated {total_rows:,} OHLCV row(s)."))
        elif invalid_pct < 0.001:
            checks.append(_warn(category, "OHLCV Integrity", f"{invalid_rows:,} anomalous OHLCV row(s) detected ({invalid_pct:.4%}).", {"invalid_rows": invalid_rows, "total_rows": total_rows}))
        else:
            checks.append(_fail(category, "OHLCV Integrity", f"{invalid_rows:,} invalid OHLCV row(s) detected ({invalid_pct:.4%}).", {"invalid_rows": invalid_rows, "total_rows": total_rows}))
    except Exception as exc:
        checks.append(_warn(category, "OHLCV Integrity", f"Could not validate OHLCV integrity: {exc}"))

    return checks


def validate_failover_readiness(db: Any) -> list[ProviderValidationCheck]:
    category = "Failover Readiness"
    checks: list[ProviderValidationCheck] = []

    telemetry_exists = _table_exists(db, "provider_telemetry")
    cache_exists = _table_exists(db, "market_data_cache")
    price_history_exists = _table_exists(db, "price_history")

    checks.append(_ok(category, "Telemetry", "Provider telemetry table is available.") if telemetry_exists else _warn(category, "Telemetry", "Provider telemetry table is not available."))

    if cache_exists or price_history_exists:
        checks.append(_ok(category, "Data Sources", "At least one market data persistence table is available.", {"market_data_cache": cache_exists, "price_history": price_history_exists}))
    else:
        checks.append(_fail(category, "Data Sources", "No market data persistence tables available."))

    provider_modules = [
        "modules.data.provider_router",
        "modules.data.provider_registry",
        "modules.market_data.provider_router",
        "modules.providers.provider_router",
        "modules.providers.provider_registry",
    ]

    found_modules: list[str] = []
    for mod in provider_modules:
        try:
            __import__(mod)
            found_modules.append(mod)
        except Exception:
            continue

    checks.append(_ok(category, "Router Modules", "Provider router/module imports are available.", {"modules": found_modules}) if found_modules else _warn(category, "Router Modules", "No known provider router module import succeeded."))

    return checks


def run_provider_validation(db: Any) -> dict[str, Any]:
    started_at = datetime.now(timezone.utc).isoformat()

    checks: list[ProviderValidationCheck] = []
    checks.extend(validate_provider_telemetry(db))
    checks.extend(validate_market_data_cache(db))
    checks.extend(validate_price_history_feed(db))
    checks.extend(validate_failover_readiness(db))

    totals = {
        "PASS": sum(1 for c in checks if c.status == "PASS"),
        "WARN": sum(1 for c in checks if c.status == "WARN"),
        "FAIL": sum(1 for c in checks if c.status == "FAIL"),
    }

    score = _score_from_counts(totals["PASS"], totals["WARN"], totals["FAIL"])
    status = _status_from_counts(totals["PASS"], totals["WARN"], totals["FAIL"])

    return {
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "score": score,
        "status": status,
        "totals": totals,
        "checks": [asdict(c) for c in checks],
    }


def provider_validation_frame(result: dict[str, Any]) -> pd.DataFrame:
    rows = result.get("checks", []) if isinstance(result, dict) else []
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    if "details" in df.columns:
        df["details"] = df["details"].apply(lambda x: str(x)[:1000])

    return df
