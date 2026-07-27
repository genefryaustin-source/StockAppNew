
"""
modules/portfolio/portfolio_validation_engine.py

Read-only Portfolio Validation Engine.

Validates:
- portfolio_positions
- portfolio_cash_ledger
- portfolio_snapshots
- closed_trades
- trade_orders
- trade_recommendations

This module does NOT write to the database or mutate application state.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

import pandas as pd
from sqlalchemy import text


@dataclass
class PortfolioValidationCheck:
    category: str
    check: str
    status: str
    severity: str
    message: str
    details: dict[str, Any] | None = None


def _ok(category: str, check: str, message: str, details: dict[str, Any] | None = None) -> PortfolioValidationCheck:
    return PortfolioValidationCheck(category, check, "PASS", "info", message, details or {})


def _warn(category: str, check: str, message: str, details: dict[str, Any] | None = None) -> PortfolioValidationCheck:
    return PortfolioValidationCheck(category, check, "WARN", "warning", message, details or {})


def _fail(category: str, check: str, message: str, details: dict[str, Any] | None = None) -> PortfolioValidationCheck:
    return PortfolioValidationCheck(category, check, "FAIL", "critical", message, details or {})


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


def _count_rows(
    db: Any,
    table_name: str,
    tenant_id: str | None = None,
    portfolio_id: str | None = None,
) -> int:
    if not _table_exists(db, table_name):
        return 0

    cols = _columns(db, table_name)
    where, params = _where_clause(cols, tenant_id=tenant_id, portfolio_id=portfolio_id)

    try:
        row = _safe_execute(
            db,
            f"SELECT COUNT(*) AS n FROM {table_name} {where}",
            params,
        ).mappings().first()
        return int(row.get("n", 0)) if row else 0
    except Exception:
        return 0


def _where_clause(
    cols: set[str],
    tenant_id: str | None = None,
    portfolio_id: str | None = None,
) -> tuple[str, dict[str, Any]]:
    clauses: list[str] = []
    params: dict[str, Any] = {}

    if tenant_id and "tenant_id" in cols:
        clauses.append("tenant_id = :tenant_id")
        params["tenant_id"] = tenant_id

    if portfolio_id and "portfolio_id" in cols:
        clauses.append("portfolio_id = :portfolio_id")
        params["portfolio_id"] = portfolio_id

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return where, params


def _first_col(cols: set[str], names: list[str]) -> str | None:
    return next((c for c in names if c in cols), None)


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


def validate_positions(
    db: Any,
    tenant_id: str | None = None,
    portfolio_id: str | None = None,
) -> list[PortfolioValidationCheck]:
    category = "Positions"
    table = "portfolio_positions"
    checks: list[PortfolioValidationCheck] = []

    if not _table_exists(db, table):
        return [_warn(category, "Table", "portfolio_positions table not found.")]

    cols = _columns(db, table)
    total = _count_rows(db, table, tenant_id=tenant_id, portfolio_id=portfolio_id)

    if total <= 0:
        return [_warn(category, "Rows", "No portfolio positions found.", {"table": table})]

    checks.append(_ok(category, "Rows", f"portfolio_positions contains {total:,} row(s).", {"rows": total}))

    symbol_col = _first_col(cols, ["symbol", "ticker", "asset_symbol", "option_symbol"])
    qty_col = _first_col(cols, ["qty", "quantity", "shares", "position_qty"])
    avg_cost_col = _first_col(cols, ["avg_cost", "avg_price", "average_cost", "cost_basis", "avg_entry_price"])
    market_value_col = _first_col(cols, ["market_value", "current_value", "position_value", "value"])

    if not symbol_col:
        checks.append(_fail(category, "Symbol Column", "No recognized symbol column in portfolio_positions.", {"columns": sorted(cols)}))
        return checks

    if not qty_col:
        checks.append(_fail(category, "Quantity Column", "No recognized quantity column in portfolio_positions.", {"columns": sorted(cols)}))
        return checks

    where, params = _where_clause(cols, tenant_id=tenant_id, portfolio_id=portfolio_id)

    try:
        rows = _safe_execute(db, f"SELECT * FROM {table} {where} LIMIT 5000", params).mappings().all()
        df = pd.DataFrame(rows)
    except Exception as exc:
        return [_fail(category, "Query", f"Failed to query portfolio positions: {exc}")]

    if df.empty:
        return [_warn(category, "Rows", "No scoped portfolio positions found.")]

    missing_symbol = df[symbol_col].isna() | (df[symbol_col].astype(str).str.strip() == "")
    checks.append(
        _fail(category, "Missing Symbols", f"{int(missing_symbol.sum())} position row(s) have missing symbols.")
        if missing_symbol.any()
        else _ok(category, "Missing Symbols", "All scoped positions have symbols.")
    )

    qty = pd.to_numeric(df[qty_col], errors="coerce")
    invalid_qty = qty.isna()
    checks.append(
        _fail(category, "Quantity Values", f"{int(invalid_qty.sum())} position row(s) have non-numeric quantity.")
        if invalid_qty.any()
        else _ok(category, "Quantity Values", "All scoped position quantities are numeric.")
    )

    negative_qty = qty < 0
    checks.append(
        _warn(
            category,
            "Negative Quantities",
            f"{int(negative_qty.sum())} position row(s) are short/negative.",
            {"note": "This can be valid for short positions/options but should be reviewed."},
        )
        if negative_qty.any()
        else _ok(category, "Negative Quantities", "No negative position quantities detected.")
    )

    if avg_cost_col:
        avg_cost = pd.to_numeric(df[avg_cost_col], errors="coerce")
        bad_cost = avg_cost.isna() | (avg_cost < 0)
        checks.append(
            _warn(category, "Cost Basis", f"{int(bad_cost.sum())} position row(s) have missing/negative cost basis.", {"column": avg_cost_col})
            if bad_cost.any()
            else _ok(category, "Cost Basis", "Cost basis values appear valid.", {"column": avg_cost_col})
        )
    else:
        checks.append(_warn(category, "Cost Basis", "No recognized cost basis column found."))

    if market_value_col:
        mv = pd.to_numeric(df[market_value_col], errors="coerce")
        bad_mv = mv.isna()
        checks.append(
            _warn(category, "Market Value", f"{int(bad_mv.sum())} position row(s) have missing/non-numeric market value.", {"column": market_value_col})
            if bad_mv.any()
            else _ok(category, "Market Value", "Market value values appear numeric.", {"column": market_value_col})
        )
    else:
        checks.append(_warn(category, "Market Value", "No recognized market value column found."))

    dup_cols = [c for c in ["portfolio_id", symbol_col] if c in df.columns]
    if len(dup_cols) >= 2:
        dups = df.duplicated(subset=dup_cols, keep=False)
        checks.append(
            _warn(category, "Duplicate Positions", f"{int(dups.sum())} duplicate portfolio/symbol position row(s) detected.", {"subset": dup_cols})
            if dups.any()
            else _ok(category, "Duplicate Positions", "No duplicate portfolio/symbol positions detected.", {"subset": dup_cols})
        )

    return checks


def validate_cash_ledger(
    db: Any,
    tenant_id: str | None = None,
    portfolio_id: str | None = None,
) -> list[PortfolioValidationCheck]:
    category = "Cash Ledger"
    table = "portfolio_cash_ledger"
    checks: list[PortfolioValidationCheck] = []

    if not _table_exists(db, table):
        return [_warn(category, "Table", "portfolio_cash_ledger table not found.")]

    cols = _columns(db, table)
    total = _count_rows(db, table, tenant_id=tenant_id, portfolio_id=portfolio_id)

    if total <= 0:
        return [_warn(category, "Rows", "No cash ledger rows found.", {"table": table})]

    checks.append(_ok(category, "Rows", f"portfolio_cash_ledger contains {total:,} row(s).", {"rows": total}))

    amount_col = _first_col(cols, ["amount", "cash_amount", "delta", "change_amount", "net_amount"])
    balance_col = _first_col(cols, ["balance", "cash_balance", "running_balance", "ending_balance"])
    created_col = _first_col(cols, ["created_at", "timestamp", "asof", "date"])

    if not amount_col and not balance_col:
        return [_warn(category, "Schema", "No amount or balance column found in cash ledger.", {"columns": sorted(cols)})]

    where, params = _where_clause(cols, tenant_id=tenant_id, portfolio_id=portfolio_id)

    try:
        rows = _safe_execute(db, f"SELECT * FROM {table} {where} LIMIT 10000", params).mappings().all()
        df = pd.DataFrame(rows)
    except Exception as exc:
        return [_fail(category, "Query", f"Failed to query cash ledger: {exc}")]

    if amount_col:
        amounts = pd.to_numeric(df[amount_col], errors="coerce")
        bad_amounts = amounts.isna()
        checks.append(
            _fail(category, "Amounts", f"{int(bad_amounts.sum())} cash ledger amount row(s) are non-numeric.", {"column": amount_col})
            if bad_amounts.any()
            else _ok(category, "Amounts", "Cash ledger amount values are numeric.", {"column": amount_col})
        )

    if balance_col:
        balances = pd.to_numeric(df[balance_col], errors="coerce")
        bad_balances = balances.isna()
        checks.append(
            _warn(category, "Balances", f"{int(bad_balances.sum())} cash ledger balance row(s) are non-numeric.", {"column": balance_col})
            if bad_balances.any()
            else _ok(category, "Balances", "Cash ledger balance values are numeric.", {"column": balance_col})
        )

    if created_col:
        latest = pd.to_datetime(df[created_col], errors="coerce").max()
        checks.append(
            _warn(category, "Freshness", "Could not determine latest cash ledger timestamp.", {"column": created_col})
            if pd.isna(latest)
            else _ok(category, "Freshness", f"Latest cash ledger record: {latest}.", {"column": created_col})
        )

    return checks


def validate_snapshots(
    db: Any,
    tenant_id: str | None = None,
    portfolio_id: str | None = None,
) -> list[PortfolioValidationCheck]:
    category = "Snapshots"
    table = "portfolio_snapshots"
    checks: list[PortfolioValidationCheck] = []

    if not _table_exists(db, table):
        return [_warn(category, "Table", "portfolio_snapshots table not found.")]

    cols = _columns(db, table)
    total = _count_rows(db, table, tenant_id=tenant_id, portfolio_id=portfolio_id)

    if total <= 0:
        return [_warn(category, "Rows", "No portfolio snapshots found.", {"table": table})]

    checks.append(_ok(category, "Rows", f"portfolio_snapshots contains {total:,} row(s).", {"rows": total}))

    value_col = _first_col(cols, ["total_value", "portfolio_value", "market_value", "equity", "nav", "value"])
    cash_col = _first_col(cols, ["cash", "cash_balance", "available_cash"])
    time_col = _first_col(cols, ["as_of", "asof", "created_at", "timestamp", "date"])

    where, params = _where_clause(cols, tenant_id=tenant_id, portfolio_id=portfolio_id)

    if value_col:
        try:
            rows = _safe_execute(db, f"SELECT {value_col} AS value FROM {table} {where} LIMIT 5000", params).mappings().all()
            df = pd.DataFrame(rows)
            vals = pd.to_numeric(df["value"], errors="coerce")
            bad = vals.isna() | (vals < 0)
            checks.append(
                _warn(category, "Portfolio Value", f"{int(bad.sum())} snapshot value row(s) are missing/negative.", {"column": value_col})
                if bad.any()
                else _ok(category, "Portfolio Value", "Snapshot portfolio values appear valid.", {"column": value_col})
            )
        except Exception as exc:
            checks.append(_warn(category, "Portfolio Value", f"Could not validate snapshot values: {exc}"))
    else:
        checks.append(_warn(category, "Portfolio Value", "No recognized portfolio value column found."))

    checks.append(_ok(category, "Cash Column", f"Snapshot cash column found: {cash_col}.") if cash_col else _warn(category, "Cash Column", "No recognized cash column found in snapshots."))

    if time_col:
        try:
            row = _safe_execute(db, f"SELECT MAX({time_col}) AS max_time FROM {table} {where}", params).mappings().first()
            max_time = row.get("max_time") if row else None
            checks.append(
                _ok(category, "Freshness", f"Latest portfolio snapshot timestamp: {max_time}.", {"column": time_col})
                if max_time
                else _warn(category, "Freshness", "No latest snapshot timestamp found.", {"column": time_col})
            )
        except Exception as exc:
            checks.append(_warn(category, "Freshness", f"Could not validate snapshot freshness: {exc}"))
    else:
        checks.append(_warn(category, "Freshness", "No recognized snapshot timestamp column found."))

    return checks


def validate_closed_trades(
    db: Any,
    tenant_id: str | None = None,
    portfolio_id: str | None = None,
) -> list[PortfolioValidationCheck]:
    category = "Closed Trades"
    table = "closed_trades"
    checks: list[PortfolioValidationCheck] = []

    if not _table_exists(db, table):
        return [_warn(category, "Table", "closed_trades table not found.")]

    cols = _columns(db, table)
    total = _count_rows(db, table, tenant_id=tenant_id, portfolio_id=portfolio_id)

    if total <= 0:
        return [_warn(category, "Rows", "No closed trades found.", {"table": table})]

    checks.append(_ok(category, "Rows", f"closed_trades contains {total:,} row(s).", {"rows": total}))

    qty_col = _first_col(cols, ["qty", "quantity", "closed_qty", "shares"])
    open_col = _first_col(cols, ["opened_at", "open_date", "entry_date", "created_at"])
    close_col = _first_col(cols, ["closed_at", "close_date", "exit_date"])
    pnl_col = _first_col(cols, ["net_pnl", "realized_pnl", "pnl", "profit_loss"])
    symbol_col = _first_col(cols, ["symbol", "ticker", "option_symbol"])

    where, params = _where_clause(cols, tenant_id=tenant_id, portfolio_id=portfolio_id)

    try:
        rows = _safe_execute(db, f"SELECT * FROM {table} {where} LIMIT 5000", params).mappings().all()
        df = pd.DataFrame(rows)
    except Exception as exc:
        return [_fail(category, "Query", f"Failed to query closed trades: {exc}")]

    if symbol_col:
        missing_symbol = df[symbol_col].isna() | (df[symbol_col].astype(str).str.strip() == "")
        checks.append(_warn(category, "Symbols", f"{int(missing_symbol.sum())} closed trade row(s) missing symbols.") if missing_symbol.any() else _ok(category, "Symbols", "Closed trade symbols are populated."))
    else:
        checks.append(_warn(category, "Symbols", "No recognized symbol column in closed_trades."))

    if qty_col:
        qty = pd.to_numeric(df[qty_col], errors="coerce")
        bad_qty = qty.isna() | (qty <= 0)
        checks.append(_warn(category, "Quantities", f"{int(bad_qty.sum())} closed trade row(s) have missing/non-positive quantities.", {"column": qty_col}) if bad_qty.any() else _ok(category, "Quantities", "Closed trade quantities appear valid.", {"column": qty_col}))
    else:
        checks.append(_warn(category, "Quantities", "No recognized quantity column in closed_trades."))

    if open_col and close_col:
        opened = pd.to_datetime(df[open_col], errors="coerce")
        closed = pd.to_datetime(df[close_col], errors="coerce")
        bad_dates = opened.notna() & closed.notna() & (opened > closed)
        checks.append(_fail(category, "Date Order", f"{int(bad_dates.sum())} closed trade row(s) have opened_at after closed_at.", {"open_col": open_col, "close_col": close_col}) if bad_dates.any() else _ok(category, "Date Order", "Closed trade date ordering is valid.", {"open_col": open_col, "close_col": close_col}))
    else:
        checks.append(_warn(category, "Date Order", "Could not find both open and close date columns."))

    if pnl_col:
        pnl = pd.to_numeric(df[pnl_col], errors="coerce")
        bad_pnl = pnl.isna()
        checks.append(_warn(category, "PnL", f"{int(bad_pnl.sum())} closed trade row(s) missing PnL.", {"column": pnl_col}) if bad_pnl.any() else _ok(category, "PnL", "Closed trade PnL values are numeric.", {"column": pnl_col}))
    else:
        checks.append(_warn(category, "PnL", "No recognized PnL column in closed_trades."))

    return checks


def validate_trade_orders(
    db: Any,
    tenant_id: str | None = None,
    portfolio_id: str | None = None,
) -> list[PortfolioValidationCheck]:
    category = "Trade Orders"
    table = "trade_orders"
    checks: list[PortfolioValidationCheck] = []

    if not _table_exists(db, table):
        return [_warn(category, "Table", "trade_orders table not found.")]

    cols = _columns(db, table)
    total = _count_rows(db, table, tenant_id=tenant_id, portfolio_id=portfolio_id)

    if total <= 0:
        return [_warn(category, "Rows", "No trade orders found.", {"table": table})]

    checks.append(_ok(category, "Rows", f"trade_orders contains {total:,} row(s).", {"rows": total}))

    status_col = _first_col(cols, ["status", "order_status"])
    qty_col = _first_col(cols, ["qty", "quantity", "shares"])
    filled_qty_col = _first_col(cols, ["filled_qty", "filled_quantity"])
    price_col = _first_col(cols, ["avg_fill_price", "filled_avg_price", "fill_price", "limit_price", "price"])

    where, params = _where_clause(cols, tenant_id=tenant_id, portfolio_id=portfolio_id)

    try:
        rows = _safe_execute(db, f"SELECT * FROM {table} {where} LIMIT 10000", params).mappings().all()
        df = pd.DataFrame(rows)
    except Exception as exc:
        return [_fail(category, "Query", f"Failed to query trade orders: {exc}")]

    if status_col:
        valid_status = {"new", "submitted", "accepted", "filled", "partially_filled", "canceled", "cancelled", "expired", "rejected", "error", "pending", "open", "closed"}
        statuses = df[status_col].astype(str).str.lower().str.strip()
        invalid = ~statuses.isin(valid_status)
        checks.append(_warn(category, "Statuses", f"{int(invalid.sum())} trade order row(s) have unrecognized status.", {"column": status_col, "sample": statuses[invalid].head(20).tolist()}) if invalid.any() else _ok(category, "Statuses", "Trade order statuses are recognized.", {"column": status_col}))
    else:
        checks.append(_warn(category, "Statuses", "No recognized status column in trade_orders."))

    if qty_col:
        qty = pd.to_numeric(df[qty_col], errors="coerce")
        bad_qty = qty.isna() | (qty <= 0)
        checks.append(_warn(category, "Quantities", f"{int(bad_qty.sum())} trade order row(s) have missing/non-positive quantities.", {"column": qty_col}) if bad_qty.any() else _ok(category, "Quantities", "Trade order quantities appear valid.", {"column": qty_col}))

    if filled_qty_col:
        filled_qty = pd.to_numeric(df[filled_qty_col], errors="coerce")
        bad_filled = filled_qty.isna() | (filled_qty < 0)
        checks.append(_warn(category, "Filled Quantities", f"{int(bad_filled.sum())} trade order row(s) have invalid filled quantity.", {"column": filled_qty_col}) if bad_filled.any() else _ok(category, "Filled Quantities", "Filled quantities are non-negative.", {"column": filled_qty_col}))

    if price_col:
        price = pd.to_numeric(df[price_col], errors="coerce")
        negative_price = price < 0
        checks.append(_fail(category, "Prices", f"{int(negative_price.sum())} trade order row(s) have negative price.", {"column": price_col}) if negative_price.any() else _ok(category, "Prices", "Trade order prices are non-negative where present.", {"column": price_col}))

    return checks


def validate_recommendations(
    db: Any,
    tenant_id: str | None = None,
    portfolio_id: str | None = None,
) -> list[PortfolioValidationCheck]:
    category = "Recommendations"
    table = "trade_recommendations"
    checks: list[PortfolioValidationCheck] = []

    if not _table_exists(db, table):
        return [_warn(category, "Table", "trade_recommendations table not found.")]

    cols = _columns(db, table)
    total = _count_rows(db, table, tenant_id=tenant_id, portfolio_id=portfolio_id)

    if total <= 0:
        return [_warn(category, "Rows", "No trade recommendations found.", {"table": table})]

    checks.append(_ok(category, "Rows", f"trade_recommendations contains {total:,} row(s).", {"rows": total}))

    score_cols = [c for c in ["conviction_score", "confidence_score", "risk_score", "quality_score", "growth_score", "value_score", "momentum_score"] if c in cols]
    if not score_cols:
        return [_warn(category, "Score Columns", "No recognized score columns found in trade_recommendations.")]

    where, params = _where_clause(cols, tenant_id=tenant_id, portfolio_id=portfolio_id)

    try:
        select_cols = ", ".join(score_cols)
        rows = _safe_execute(db, f"SELECT {select_cols} FROM {table} {where} LIMIT 5000", params).mappings().all()
        df = pd.DataFrame(rows)
    except Exception as exc:
        return [_warn(category, "Score Query", f"Could not query recommendation score columns: {exc}")]

    bad_details: dict[str, int] = {}
    for col in score_cols:
        vals = pd.to_numeric(df[col], errors="coerce")
        bad = vals.notna() & ((vals < 0) | (vals > 100))
        if bad.any():
            bad_details[col] = int(bad.sum())

    checks.append(_fail(category, "Score Ranges", "Recommendation score values outside 0-100 range detected.", bad_details) if bad_details else _ok(category, "Score Ranges", "Recommendation score values are within 0-100 range.", {"columns": score_cols}))

    checks.append(_ok(category, "Execution Flag", "Recommendation execution flag column found.") if "executed" in cols else _warn(category, "Execution Flag", "No executed flag column found in recommendations."))

    return checks


def run_portfolio_validation(
    db: Any,
    tenant_id: str | None = None,
    portfolio_id: str | None = None,
) -> dict[str, Any]:
    started_at = datetime.now(timezone.utc).isoformat()

    checks: list[PortfolioValidationCheck] = []
    checks.extend(validate_positions(db, tenant_id=tenant_id, portfolio_id=portfolio_id))
    checks.extend(validate_cash_ledger(db, tenant_id=tenant_id, portfolio_id=portfolio_id))
    checks.extend(validate_snapshots(db, tenant_id=tenant_id, portfolio_id=portfolio_id))
    checks.extend(validate_closed_trades(db, tenant_id=tenant_id, portfolio_id=portfolio_id))
    checks.extend(validate_trade_orders(db, tenant_id=tenant_id, portfolio_id=portfolio_id))
    checks.extend(validate_recommendations(db, tenant_id=tenant_id, portfolio_id=portfolio_id))

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
        "portfolio_id": portfolio_id,
        "score": score,
        "status": status,
        "totals": totals,
        "checks": [asdict(c) for c in checks],
    }


def portfolio_validation_frame(result: dict[str, Any]) -> pd.DataFrame:
    rows = result.get("checks", []) if isinstance(result, dict) else []
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    if "details" in df.columns:
        df["details"] = df["details"].apply(lambda x: str(x)[:1000])

    return df
