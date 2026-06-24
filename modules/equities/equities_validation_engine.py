"""
modules/equities_validation_engine.py

Read-only Equities Validation Engine.

Validates the core stock/equities platform data layers:
- prices
- fundamentals
- recommendations
- earnings
- ownership

Designed to be defensive against schema differences across local/Postgres deployments.
This module does NOT write to the database or mutate application state.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import math
import pandas as pd
from sqlalchemy import text


DEFAULT_SYMBOLS = ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "TSLA"]


@dataclass
class EquitiesValidationCheck:
    category: str
    check: str
    status: str
    severity: str
    message: str
    details: dict[str, Any] | None = None


def _ok(category: str, check: str, message: str, details: dict[str, Any] | None = None) -> EquitiesValidationCheck:
    return EquitiesValidationCheck(category, check, "PASS", "info", message, details or {})


def _warn(category: str, check: str, message: str, details: dict[str, Any] | None = None) -> EquitiesValidationCheck:
    return EquitiesValidationCheck(category, check, "WARN", "warning", message, details or {})


def _fail(category: str, check: str, message: str, details: dict[str, Any] | None = None) -> EquitiesValidationCheck:
    return EquitiesValidationCheck(category, check, "FAIL", "critical", message, details or {})


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


def _count_rows(db: Any, table_name: str, tenant_id: str | None = None) -> int:
    cols = _columns(db, table_name)
    try:
        if tenant_id and "tenant_id" in cols:
            row = _safe_execute(
                db,
                f"SELECT COUNT(*) AS n FROM {table_name} WHERE tenant_id = :tenant_id",
                {"tenant_id": tenant_id},
            ).mappings().first()
        else:
            row = _safe_execute(db, f"SELECT COUNT(*) AS n FROM {table_name}").mappings().first()
        return int(row.get("n", 0)) if row else 0
    except Exception:
        return 0


def _first_available_table(db: Any, candidates: list[str]) -> str | None:
    for table in candidates:
        if _table_exists(db, table):
            return table
    return None


def _symbols_clause(symbols: list[str]) -> tuple[str, dict[str, Any]]:
    clean = [str(s or "").upper().strip() for s in symbols if str(s or "").strip()]
    if not clean:
        clean = DEFAULT_SYMBOLS

    params = {f"sym_{i}": s for i, s in enumerate(clean)}
    clause = ", ".join(f":sym_{i}" for i in range(len(clean)))
    return clause, params


def _status_from_counts(pass_count: int, warn_count: int, fail_count: int) -> str:
    if fail_count:
        return "FAIL"
    if warn_count:
        return "WARN"
    return "PASS"


def _score_from_counts(pass_count: int, warn_count: int, fail_count: int) -> float:
    total = pass_count + warn_count + fail_count
    if total <= 0:
        return 0.0
    return round(((pass_count + warn_count * 0.5) / total) * 100.0, 2)


def validate_prices(
    db: Any,
    symbols: list[str] | None = None,
    tenant_id: str | None = None,
    stale_days: int = 5,
) -> list[EquitiesValidationCheck]:
    category = "Prices"
    symbols = symbols or DEFAULT_SYMBOLS
    checks: list[EquitiesValidationCheck] = []

    candidate_tables = [
        "price_history",
        "latest_prices",
        "price_snapshots",
        "market_prices",
        "equity_prices",
        "market_data_cache",
    ]

    table = None

    for t in candidate_tables:

        if not _table_exists(db, t):
            continue

        row_count = _count_rows(
            db,
            t,
            tenant_id=tenant_id,
        )

        if row_count > 0:
            table = t
            break

    if not table:
        return [
            _fail(
                category,
                "Table",
                "No recognized price table found.",
            )
        ]

    cols = _columns(db, table)
    total = _count_rows(db, table, tenant_id=tenant_id)
    # =====================================================
    # PRICE HISTORY SPECIAL VALIDATION
    # =====================================================

    if table == "price_history":

        try:

            # ---------------------------------------------
            # OHLC VALIDATION
            # ---------------------------------------------

            ohlc_row = _safe_execute(
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
                            THEN 1
                            ELSE 0
                        END
                    ) AS invalid_rows
                FROM price_history
                """
            ).mappings().first()

            invalid_rows = int(
                ohlc_row.get("invalid_rows") or 0
            )

            total_rows = int(
                ohlc_row.get("total_rows") or 0
            )

            failure_pct = (
                invalid_rows / total_rows
                if total_rows > 0
                else 0.0
            )

            if invalid_rows == 0:

                checks.append(
                    _ok(
                        category,
                        "OHLC Integrity",
                        f"Validated {total_rows:,} OHLC rows."
                    )
                )

            elif failure_pct < 0.001:

                checks.append(
                    _warn(
                        category,
                        "OHLC Integrity",
                        f"{invalid_rows:,} anomalous OHLC row(s) detected "
                        f"({failure_pct:.4%} of dataset).",
                        {
                            "invalid_rows": invalid_rows,
                            "total_rows": total_rows,
                            "failure_pct": failure_pct,
                        }
                    )
                )

            elif failure_pct < 0.01:

                checks.append(
                    _warn(
                        category,
                        "OHLC Integrity",
                        f"{invalid_rows:,} OHLC row(s) failed validation "
                        f"({failure_pct:.4%} of dataset).",
                        {
                            "invalid_rows": invalid_rows,
                            "total_rows": total_rows,
                            "failure_pct": failure_pct,
                        }
                    )
                )

            else:

                checks.append(
                    _fail(
                        category,
                        "OHLC Integrity",
                        f"{invalid_rows:,} invalid OHLC row(s) detected "
                        f"({failure_pct:.4%} of dataset).",
                        {
                            "invalid_rows": invalid_rows,
                            "total_rows": total_rows,
                            "failure_pct": failure_pct,
                        }
                    )
                )

            # ---------------------------------------------
            # VOLUME VALIDATION
            # ---------------------------------------------

            volume_row = _safe_execute(
                db,
                """
                SELECT
                    COUNT(*) AS invalid_volume
                FROM price_history
                WHERE volume < 0
                """
            ).mappings().first()

            invalid_volume = int(
                volume_row.get("invalid_volume") or 0
            )

            if invalid_volume == 0:

                checks.append(
                    _ok(
                        category,
                        "Volume Integrity",
                        "No negative volumes detected."
                    )
                )

            else:

                checks.append(
                    _fail(
                        category,
                        "Volume Integrity",
                        f"{invalid_volume:,} negative volume rows detected."
                    )
                )

            # ---------------------------------------------
            # FRESHNESS VALIDATION
            # ---------------------------------------------

            freshness_row = _safe_execute(
                db,
                """
                SELECT MAX(date) AS latest_date
                FROM price_history
                """
            ).mappings().first()

            latest_date = freshness_row.get(
                "latest_date"
            )

            if latest_date:

                age_days = (
                        datetime.utcnow().date()
                        - latest_date
                ).days

                if age_days <= stale_days:

                    checks.append(
                        _ok(
                            category,
                            "Freshness",
                            f"Latest price history is {age_days} day(s) old."
                        )
                    )

                elif age_days <= 30:

                    checks.append(
                        _warn(
                            category,
                            "Freshness",
                            f"Price history is {age_days} day(s) old."
                        )
                    )

                else:

                    checks.append(
                        _fail(
                            category,
                            "Freshness",
                            f"Price history is stale ({age_days} days old)."
                        )
                    )

        except Exception as exc:

            checks.append(
                _warn(
                    category,
                    "Price History Validation",
                    f"Could not run advanced validation: {exc}"
                )
            )
    if total <= 0:
        return [_fail(category, "Rows", f"{table} exists but contains no rows.")]

    checks.append(_ok(category, "Rows", f"{table} contains {total:,} row(s).", {"table": table, "rows": total}))

    symbol_col = "symbol" if "symbol" in cols else None
    price_col = next(
        (
            c
            for c in [
            "close",
            "price",
            "last_price",
            "current_price",
            "latest_price",
        ]
            if c in cols
        ),
        None,
    )
    time_col = next((c for c in ["asof", "captured_at", "updated_at", "created_at", "timestamp", "date"] if c in cols), None)

    if not symbol_col:
        checks.append(_warn(category, "Symbol Column", f"{table} has no symbol column."))
        return checks

    if not price_col:
        checks.append(_fail(category, "Price Column", f"{table} has no recognized price column.", {"columns": sorted(cols)}))
        return checks

    clause, params = _symbols_clause(symbols)

    try:
        rows = _safe_execute(
            db,
            f"""
            SELECT symbol, {price_col} AS price
            FROM {table}
            WHERE UPPER(symbol) IN ({clause})
            ORDER BY symbol
            LIMIT 500
            """,
            params,
        ).mappings().all()

        df = pd.DataFrame(rows)
    except Exception as exc:
        return [_fail(category, "Sample Query", f"Failed to query price sample: {exc}", {"table": table})]

    if df.empty:
        checks.append(_warn(category, "Sample Coverage", "No tracked sample symbols found in price table.", {"symbols": symbols}))
    else:
        df["price"] = pd.to_numeric(df["price"], errors="coerce")
        bad = df[df["price"].isna() | (df["price"] <= 0)]
        if bad.empty:
            checks.append(_ok(category, "Price Values", f"{len(df)} sample price row(s) are positive.", {"sample": df.head(20).to_dict("records")}))
        else:
            checks.append(_fail(category, "Price Values", f"{len(bad)} sample price row(s) are missing or non-positive.", {"sample": bad.head(20).to_dict("records")}))

    if time_col:
        try:
            row = _safe_execute(
                db,
                f"SELECT MAX({time_col}) AS max_time FROM {table}",
            ).mappings().first()
            max_time = row.get("max_time") if row else None
            if max_time:
                if hasattr(max_time, "replace"):
                    now = datetime.now(timezone.utc)
                    if getattr(max_time, "tzinfo", None) is None:
                        max_time_cmp = max_time.replace(tzinfo=timezone.utc)
                    else:
                        max_time_cmp = max_time
                    age_days = (now - max_time_cmp).total_seconds() / 86400
                    if age_days <= stale_days:
                        checks.append(_ok(category, "Freshness", f"Latest price data is {age_days:.1f} day(s) old.", {"latest": str(max_time), "time_col": time_col}))
                    else:
                        checks.append(_warn(category, "Freshness", f"Latest price data appears stale: {age_days:.1f} day(s) old.", {"latest": str(max_time), "time_col": time_col}))
                else:
                    checks.append(_ok(category, "Freshness", f"Latest price timestamp found: {max_time}", {"time_col": time_col}))
            else:
                checks.append(_warn(category, "Freshness", f"No max timestamp found in {time_col}."))
        except Exception as exc:
            checks.append(_warn(category, "Freshness", f"Could not validate price freshness: {exc}"))
    else:
        checks.append(_warn(category, "Freshness", "No recognized timestamp column for price freshness."))

    return checks


def validate_fundamentals(
    db: Any,
    symbols: list[str] | None = None,
    tenant_id: str | None = None,
) -> list[EquitiesValidationCheck]:
    category = "Fundamentals"
    symbols = symbols or DEFAULT_SYMBOLS
    checks: list[EquitiesValidationCheck] = []

    table = _first_available_table(
        db,
        [
            "fundamental_snapshots",
            "financial_periods",
            "financial_snapshots",
            "company_fundamentals",
            "fundamentals",
        ],
    )

    if not table:
        return [_fail(category, "Table", "No recognized fundamentals table found.")]

    cols = _columns(db, table)
    total = _count_rows(db, table, tenant_id=tenant_id)

    if total <= 0:
        return [_warn(category, "Rows", f"{table} exists but contains no rows.", {"table": table})]

    checks.append(_ok(category, "Rows", f"{table} contains {total:,} row(s).", {"table": table, "rows": total}))

    if "symbol" not in cols:
        checks.append(_warn(category, "Symbol Column", f"{table} has no symbol column."))
        return checks

    quality_cols = [
        "gross_margin",
        "operating_margin",
        "fcf_margin",
        "revenue_cagr",
        "roic",
        "roe",
        "debt_to_equity",
        "current_ratio",
        "eps",
        "revenue",
        "free_cash_flow",
    ]
    available_metrics = [c for c in quality_cols if c in cols]

    if not available_metrics:
        checks.append(_warn(category, "Metric Columns", "No recognized fundamental metric columns found.", {"columns": sorted(cols)}))
    else:
        checks.append(_ok(category, "Metric Columns", f"{len(available_metrics)} recognized metric column(s) found.", {"metrics": available_metrics}))

    clause, params = _symbols_clause(symbols)

    try:
        metric_select = ", ".join(available_metrics[:8]) if available_metrics else "symbol"
        rows = _safe_execute(
            db,
            f"""
            SELECT symbol, {metric_select}
            FROM {table}
            WHERE UPPER(symbol) IN ({clause})
            LIMIT 500
            """,
            params,
        ).mappings().all()
        df = pd.DataFrame(rows)
    except Exception as exc:
        checks.append(_warn(category, "Sample Query", f"Failed to query fundamentals sample: {exc}", {"table": table}))
        return checks

    if df.empty:
        checks.append(_warn(category, "Sample Coverage", "No tracked sample symbols found in fundamentals table.", {"symbols": symbols}))
    else:
        numeric_cols = [c for c in df.columns if c != "symbol"]
        populated = 0
        possible = 0
        for col in numeric_cols:
            vals = pd.to_numeric(df[col], errors="coerce")
            populated += int(vals.notna().sum())
            possible += len(vals)
        coverage = populated / possible if possible else 0
        if coverage >= 0.70:
            checks.append(_ok(category, "Metric Coverage", f"Fundamental metric coverage is {coverage:.1%}.", {"rows": len(df), "coverage": coverage}))
        elif coverage >= 0.35:
            checks.append(_warn(category, "Metric Coverage", f"Fundamental metric coverage is partial: {coverage:.1%}.", {"rows": len(df), "coverage": coverage}))
        else:
            checks.append(_fail(category, "Metric Coverage", f"Fundamental metric coverage is weak: {coverage:.1%}.", {"rows": len(df), "coverage": coverage}))

    return checks


def validate_recommendations(
    db: Any,
    tenant_id: str | None = None,
) -> list[EquitiesValidationCheck]:
    category = "Recommendations"
    checks: list[EquitiesValidationCheck] = []

    table = _first_available_table(
        db,
        [
            "trade_recommendations",
            "stock_recommendations",
            "recommendations",
            "discovered_strategies",
        ],
    )

    if not table:
        return [_warn(category, "Table", "No recognized recommendations table found.")]

    cols = _columns(db, table)
    total = _count_rows(db, table, tenant_id=tenant_id)

    if total <= 0:
        return [_warn(category, "Rows", f"{table} exists but has no recommendations.", {"table": table})]

    checks.append(_ok(category, "Rows", f"{table} contains {total:,} recommendation row(s).", {"table": table, "rows": total}))

    needed = ["symbol", "recommendation", "conviction_score", "confidence_score"]
    present = [c for c in needed if c in cols]
    missing = [c for c in needed if c not in cols]

    if missing:
        checks.append(_warn(category, "Schema", f"Recommendation table is missing optional/expected columns: {missing}", {"present": present}))
    else:
        checks.append(_ok(category, "Schema", "Recommendation table has core recommendation columns."))

    score_cols = [c for c in ["conviction_score", "confidence_score", "risk_reward", "current_price", "entry_price", "target_price", "stop_price"] if c in cols]
    if score_cols:
        try:
            select_cols = ", ".join(score_cols)
            where = "WHERE tenant_id = :tenant_id" if tenant_id and "tenant_id" in cols else ""
            params = {"tenant_id": tenant_id} if tenant_id and "tenant_id" in cols else {}
            rows = _safe_execute(
                db,
                f"SELECT {select_cols} FROM {table} {where} ORDER BY created_at DESC NULLS LAST LIMIT 500",
                params,
            ).mappings().all()
            df = pd.DataFrame(rows)
            if not df.empty:
                bad_details = {}
                for col in score_cols:
                    vals = pd.to_numeric(df[col], errors="coerce")
                    if col in ["conviction_score", "confidence_score"]:
                        bad = vals[(vals < 0) | (vals > 100)]
                        if len(bad):
                            bad_details[col] = int(len(bad))
                if bad_details:
                    checks.append(_fail(category, "Score Ranges", "One or more recommendation score columns are outside expected 0-100 range.", bad_details))
                else:
                    checks.append(_ok(category, "Score Ranges", "Recommendation score columns appear numerically sane.", {"checked": score_cols}))
        except Exception as exc:
            checks.append(_warn(category, "Score Ranges", f"Could not validate recommendation scores: {exc}"))

    return checks


def validate_earnings(
    db: Any,
    symbols: list[str] | None = None,
    tenant_id: str | None = None,
) -> list[EquitiesValidationCheck]:
    category = "Earnings"
    symbols = symbols or DEFAULT_SYMBOLS
    checks: list[EquitiesValidationCheck] = []

    table = _first_available_table(
        db,
        [
            "earnings_events",
            "earnings_calendar",
            "earnings_snapshots",
            "earnings",
        ],
    )

    if not table:
        return [_warn(category, "Table", "No recognized earnings table found.")]

    cols = _columns(db, table)
    total = _count_rows(db, table, tenant_id=tenant_id)

    if total <= 0:
        return [_warn(category, "Rows", f"{table} exists but contains no rows.", {"table": table})]

    checks.append(_ok(category, "Rows", f"{table} contains {total:,} earnings row(s).", {"table": table, "rows": total}))

    date_col = next((c for c in ["earnings_date", "report_date", "date", "event_date", "fiscal_date_ending"] if c in cols), None)
    if not date_col:
        checks.append(_warn(category, "Date Column", "No recognized earnings date column found.", {"columns": sorted(cols)}))
        return checks

    try:
        row = _safe_execute(
            db,
            f"SELECT MIN({date_col}) AS min_date, MAX({date_col}) AS max_date FROM {table}",
        ).mappings().first()
        if row:
            checks.append(_ok(category, "Date Range", "Earnings date range calculated.", {"min": str(row.get("min_date")), "max": str(row.get("max_date")), "date_col": date_col}))
    except Exception as exc:
        checks.append(_warn(category, "Date Range", f"Could not validate earnings date range: {exc}"))

    if "symbol" in cols:
        clause, params = _symbols_clause(symbols)
        try:
            n = _safe_execute(
                db,
                f"SELECT COUNT(*) AS n FROM {table} WHERE UPPER(symbol) IN ({clause})",
                params,
            ).mappings().first()
            sample_count = int(n.get("n", 0)) if n else 0
            if sample_count > 0:
                checks.append(_ok(category, "Sample Coverage", f"{sample_count} earnings row(s) found for tracked sample symbols.", {"symbols": symbols}))
            else:
                checks.append(_warn(category, "Sample Coverage", "No earnings rows found for tracked sample symbols.", {"symbols": symbols}))
        except Exception as exc:
            checks.append(_warn(category, "Sample Coverage", f"Could not validate earnings sample coverage: {exc}"))

    return checks


def validate_ownership(
    db: Any,
    symbols: list[str] | None = None,
    tenant_id: str | None = None,
) -> list[EquitiesValidationCheck]:
    category = "Ownership"
    symbols = symbols or DEFAULT_SYMBOLS
    checks: list[EquitiesValidationCheck] = []

    ownership_tables = [
        "institutional_holdings",
        "insider_transactions",
    ]

    existing = [t for t in ownership_tables if _table_exists(db, t)]

    if not existing:
        return [_warn(category, "Tables", "No institutional_holdings or insider_transactions table found.")]

    for table in existing:
        cols = _columns(db, table)
        total = _count_rows(db, table, tenant_id=tenant_id)

        if total <= 0:
            checks.append(_warn(category, table, f"{table} exists but contains no rows.", {"table": table}))
            continue

        checks.append(_ok(category, table, f"{table} contains {total:,} row(s).", {"table": table, "rows": total}))

        if "symbol" in cols:
            clause, params = _symbols_clause(symbols)
            try:
                n = _safe_execute(
                    db,
                    f"SELECT COUNT(*) AS n FROM {table} WHERE UPPER(symbol) IN ({clause})",
                    params,
                ).mappings().first()
                sample_count = int(n.get("n", 0)) if n else 0
                if sample_count > 0:
                    checks.append(_ok(category, f"{table} Sample", f"{sample_count} row(s) found for tracked sample symbols.", {"symbols": symbols}))
                else:
                    checks.append(_warn(category, f"{table} Sample", "No rows found for tracked sample symbols.", {"symbols": symbols}))
            except Exception as exc:
                checks.append(_warn(category, f"{table} Sample", f"Could not validate sample coverage: {exc}"))

    return checks


def run_equities_validation(
    db: Any,
    tenant_id: str | None = None,
    symbols: list[str] | None = None,
) -> dict[str, Any]:
    started_at = datetime.now(timezone.utc).isoformat()
    symbols = symbols or DEFAULT_SYMBOLS

    checks: list[EquitiesValidationCheck] = []
    checks.extend(validate_prices(db, symbols=symbols, tenant_id=tenant_id))
    checks.extend(validate_fundamentals(db, symbols=symbols, tenant_id=tenant_id))
    checks.extend(validate_recommendations(db, tenant_id=tenant_id))
    checks.extend(validate_earnings(db, symbols=symbols, tenant_id=tenant_id))
    checks.extend(validate_ownership(db, symbols=symbols, tenant_id=tenant_id))

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
        "tenant_id": tenant_id,
        "symbols": symbols,
        "score": score,
        "status": status,
        "totals": totals,
        "checks": [asdict(c) for c in checks],
    }


def equities_validation_frame(result: dict[str, Any]) -> pd.DataFrame:
    rows = result.get("checks", []) if isinstance(result, dict) else []
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    if "details" in df.columns:
        df["details"] = df["details"].apply(lambda x: str(x)[:1000])

    return df
