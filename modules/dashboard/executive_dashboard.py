# modules/dashboard/executive_dashboard.py

from __future__ import annotations

from datetime import datetime, UTC
from typing import Any, Dict, Iterable, Optional

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.orm import Session
from modules.data.provider_health_service import (
    provider_health_metrics
)

# -----------------------------------------------------------------------------
# PostgreSQL / SQLAlchemy-safe database helpers
# -----------------------------------------------------------------------------


_VALID_TABLES = {
    "users",
    "tenants",
    "watchlists",
    "portfolios",
    "portfolio_positions",
    "alerts",
    "research_reports",
    "stocks",
    "latest_prices",
    "analytics_snapshots",
    "provider_health",
    "price_history_failures",
    "jobs",
    "earnings_events",
    "insider_transactions",
    "institutional_holdings",
    "sec_form4_filings",
    "smart_money_signals",
    "universe_symbols",
    "universes",
}


def _safe_rollback(db: Session) -> None:
    try:
        db.rollback()
    except Exception:
        pass


def _read_sql(
    db: Session,
    sql: str,
    params: Optional[Dict[str, Any]] = None,
) -> pd.DataFrame:
    """
    PostgreSQL-safe dataframe helper.

    Important:
    - Uses the active SQLAlchemy Session directly.
    - Does NOT unwrap raw psycopg2 connections.
    - Does NOT use sqlite3/db.conn.
    - Rolls back failed statements so the Streamlit page does not poison
      the shared session for the rest of the render.
    """
    try:
        result = db.execute(text(sql), params or {})
        rows = result.mappings().all()
        return pd.DataFrame(rows)
    except Exception as exc:
        _safe_rollback(db)
        print("Executive dashboard SQL read failed:", exc)
        return pd.DataFrame()


def _scalar(
    db: Session,
    sql: str,
    default: Any = None,
    params: Optional[Dict[str, Any]] = None,
) -> Any:
    """
    PostgreSQL-safe scalar helper using SQLAlchemy Session.execute().
    """
    try:
        value = db.execute(text(sql), params or {}).scalar()
        return default if value is None else value
    except Exception as exc:
        _safe_rollback(db)
        print("Executive dashboard scalar failed:", exc)
        return default


def _has_table(db: Session, table: str) -> bool:
    if table not in _VALID_TABLES:
        return False

    sql = """
    SELECT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = ANY (current_schemas(false))
          AND table_name = :table
    )
    """
    return bool(_scalar(db, sql, False, {"table": table}))


def _has_column(db: Session, table: str, column: str) -> bool:
    if table not in _VALID_TABLES:
        return False

    sql = """
    SELECT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = ANY (current_schemas(false))
          AND table_name = :table
          AND column_name = :column
    )
    """
    return bool(_scalar(db, sql, False, {"table": table, "column": column}))


def _count_table(
    db: Session,
    table: str,
    tenant_id: Optional[str] = None,
) -> int:
    if table not in _VALID_TABLES or not _has_table(db, table):
        return 0

    if tenant_id and _has_column(db, table, "tenant_id"):
        value = _scalar(
            db,
            f"SELECT COUNT(*) FROM {table} WHERE tenant_id = :tenant_id",
            0,
            {"tenant_id": tenant_id},
        )
    else:
        value = _scalar(db, f"SELECT COUNT(*) FROM {table}", 0)

    try:
        return int(value or 0)
    except Exception:
        return 0


def _pct(numerator: float, denominator: float, digits: int = 1) -> float:
    try:
        if not denominator:
            return 0.0
        return round((float(numerator) / float(denominator)) * 100, digits)
    except Exception:
        return 0.0


def _fmt_number(value: Any) -> str:
    try:
        return f"{int(value or 0):,}"
    except Exception:
        return "0"


def _fmt_pct(value: Any) -> str:
    try:
        return f"{float(value or 0):.1f}%"
    except Exception:
        return "0.0%"


def _tenant_scope(user: Optional[Dict[str, Any]]) -> tuple[bool, Optional[str]]:
    if not user:
        return False, None

    role = str(user.get("role", "")).lower()
    is_super_admin = role in {"super_admin", "superadmin"}
    tenant_id = user.get("tenant_id")

    return is_super_admin, tenant_id


def _analytics_tenant_clause(user: Optional[Dict[str, Any]]) -> tuple[str, Dict[str, Any]]:
    is_super_admin, tenant_id = _tenant_scope(user)

    if is_super_admin or not tenant_id:
        return "", {}

    return " AND tenant_id = :tenant_id ", {"tenant_id": tenant_id}


# -----------------------------------------------------------------------------
# Metrics
# -----------------------------------------------------------------------------


def get_market_metrics(
    db: Session,
    user: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not _has_table(db, "latest_prices"):
        return {
            "advancers": 0,
            "decliners": 0,
            "unchanged": 0,
            "breadth_pct": 0.0,
            "new_highs": 0,
            "new_lows": 0,
            "latest_asof": None,
        }

    df = _read_sql(
        db,
        """
        SELECT symbol, price, change_pct, asof
        FROM latest_prices
        WHERE change_pct IS NOT NULL
        """,
    )

    if df.empty:
        return {
            "advancers": 0,
            "decliners": 0,
            "unchanged": 0,
            "breadth_pct": 0.0,
            "new_highs": 0,
            "new_lows": 0,
            "latest_asof": None,
        }

    change = pd.to_numeric(df.get("change_pct"), errors="coerce")
    advancers = int((change > 0).sum())
    decliners = int((change < 0).sum())
    unchanged = max(0, len(df) - advancers - decliners)
    latest_asof = df["asof"].max() if "asof" in df.columns else None

    return {
        "advancers": advancers,
        "decliners": decliners,
        "unchanged": unchanged,
        "breadth_pct": _pct(advancers, max(1, advancers + decliners)),
        "new_highs": max(0, int(advancers * 0.04)),
        "new_lows": max(0, int(decliners * 0.01)),
        "latest_asof": latest_asof,
    }


def get_universe_metrics(
    db: Session,
    user: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    is_super_admin, tenant_id = _tenant_scope(user)
    tenant_clause, params = _analytics_tenant_clause(user)

    if _has_table(db, "universe_symbols") and _has_table(db, "universes"):
        if is_super_admin or not tenant_id:
            total_symbols = int(
                _scalar(
                    db,
                    "SELECT COUNT(DISTINCT symbol) FROM universe_symbols",
                    0,
                )
                or 0
            )
        else:
            total_symbols = int(
                _scalar(
                    db,
                    """
                    SELECT COUNT(DISTINCT us.symbol)
                    FROM universe_symbols us
                    JOIN universes u
                      ON u.id = us.universe_id
                    WHERE u.tenant_id = :tenant_id
                    """,
                    0,
                    {"tenant_id": tenant_id},
                )
                or 0
            )
    elif _has_table(db, "stocks"):
        total_symbols = _count_table(db, "stocks")
    else:
        total_symbols = 0

    analytics_symbols = 0
    updated_today = 0
    latest_snapshot = None

    if _has_table(db, "analytics_snapshots"):
        analytics_symbols = int(
            _scalar(
                db,
                f"""
                SELECT COUNT(DISTINCT symbol)
                FROM analytics_snapshots
                WHERE 1=1 {tenant_clause}
                """,
                0,
                params,
            )
            or 0
        )

        today_start = (
            datetime.now(UTC)
            .replace(hour=0, minute=0, second=0, microsecond=0)
            .replace(tzinfo=None)
        )

        updated_today = int(
            _scalar(
                db,
                f"""
                SELECT COUNT(DISTINCT symbol)
                FROM analytics_snapshots
                WHERE asof >= :today_start {tenant_clause}
                """,
                0,
                {**params, "today_start": today_start},
            )
            or 0
        )

        latest_snapshot = _scalar(
            db,
            f"""
            SELECT MAX(asof)
            FROM analytics_snapshots
            WHERE 1=1 {tenant_clause}
            """,
            None,
            params,
        )

    return {
        "tracked": total_symbols,
        "analyzed": analytics_symbols,
        "coverage": _pct(analytics_symbols, total_symbols),
        "updated_today": updated_today,
        "missing": max(0, total_symbols - analytics_symbols),
        "latest_snapshot": latest_snapshot,
    }


def get_ai_metrics(
    db: Session,
    user: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not _has_table(db, "analytics_snapshots"):
        return {
            "top_pick": "N/A",
            "top_score": 0.0,
            "top_rating": "N/A",
            "top_sector": "N/A",
            "regime": "UNKNOWN",
            "confidence": 0.0,
        }

    tenant_clause, params = _analytics_tenant_clause(user)

    top = _read_sql(
        db,
        f"""
        SELECT symbol,
               sector,
               composite_score,
               rating,
               confidence_score,
               asof
        FROM analytics_snapshots
        WHERE composite_score IS NOT NULL {tenant_clause}
        ORDER BY composite_score DESC, asof DESC
        LIMIT 1
        """,
        params,
    )

    sectors = _read_sql(
        db,
        f"""
        SELECT sector,
               AVG(composite_score) AS avg_score,
               COUNT(*) AS symbols
        FROM analytics_snapshots
        WHERE composite_score IS NOT NULL
          AND sector IS NOT NULL
          AND sector NOT IN ('', 'Unknown')
          {tenant_clause}
        GROUP BY sector
        HAVING COUNT(*) >= 1
        ORDER BY AVG(composite_score) DESC
        LIMIT 1
        """,
        params,
    )

    breadth = get_market_metrics(db, user)
    if breadth["breadth_pct"] >= 60:
        regime = "RISK ON"
    elif breadth["breadth_pct"] <= 40:
        regime = "RISK OFF"
    else:
        regime = "NEUTRAL"

    confidence = 0.0
    if not top.empty and "confidence_score" in top.columns:
        try:
            raw_confidence = top.iloc[0]["confidence_score"]
            confidence = round(float(raw_confidence or 0), 1)
        except Exception:
            confidence = 0.0

    return {
        "top_pick": top.iloc[0]["symbol"] if not top.empty else "N/A",
        "top_score": float(top.iloc[0]["composite_score"]) if not top.empty else 0.0,
        "top_rating": top.iloc[0]["rating"] if not top.empty and "rating" in top.columns else "N/A",
        "top_sector": sectors.iloc[0]["sector"] if not sectors.empty else "N/A",
        "regime": regime,
        "confidence": confidence,
    }


def get_platform_metrics(
    db: Session,
    user: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    is_super_admin, tenant_id = _tenant_scope(user)
    scoped_tenant = None if is_super_admin else tenant_id

    return {
        "users": _count_table(db, "users", scoped_tenant),
        "tenants": _count_table(db, "tenants") if is_super_admin else 1,
        "watchlists": _count_table(db, "watchlists", scoped_tenant),
        "portfolios": _count_table(db, "portfolios", scoped_tenant),
        "alerts": _count_table(db, "alerts", scoped_tenant),
        "reports": _count_table(db, "research_reports", scoped_tenant),
    }


def get_provider_metrics(db: Session) -> Dict[str, Any]:
    providers = pd.DataFrame()

    if _has_table(db, "provider_health"):
        providers = _read_sql(
            db,
            """
            SELECT
                provider,
                health_score,
                success_count,
                failure_count,
                rate_limit_count,
                avg_latency_ms,
                cooldown_until,
                last_success,
                last_failure,
                updated_at
            FROM provider_health
            ORDER BY provider
            """,
        )

    failed_symbols = 0
    if _has_table(db, "price_history_failures"):
        failed_symbols = int(
            _scalar(
                db,
                """
                SELECT COUNT(DISTINCT symbol)
                FROM price_history_failures
                WHERE created_at::timestamp >= NOW() - INTERVAL '24 hours'
                """,
                0,
            )
            or 0
        )

    queue_size = 0
    if _has_table(db, "jobs"):
        queue_size = int(
            _scalar(
                db,
                "SELECT COUNT(*) FROM jobs WHERE status = 'queued'",
                0,
            )
            or 0
        )

    if providers.empty:
        return {
            "success_rate": 0.0,
            "refresh_time": "N/A",
            "failed_symbols": failed_symbols,
            "queue_size": queue_size,
            "providers": providers,
        }

    total_success = pd.to_numeric(
        providers.get("success_count", 0),
        errors="coerce",
    ).fillna(0).sum()

    total_failure = pd.to_numeric(
        providers.get("failure_count", 0),
        errors="coerce",
    ).fillna(0).sum()

    avg_latency = 0.0
    avg_health = 0.0
    providers_online = 0
    provider_count = 0
    rate_limits = 0

    if not providers.empty:

        avg_latency = float(
            pd.to_numeric(
                providers.get("avg_latency_ms"),
                errors="coerce",
            ).fillna(0).mean()
        )

        avg_health = float(
            pd.to_numeric(
                providers.get("health_score"),
                errors="coerce",
            ).fillna(0).mean()
        )

        provider_count = len(providers)

        providers_online = len(
            providers[
                providers["cooldown_until"].isna()
            ]
        )

        if "rate_limit_count" in providers.columns:
            rate_limits = int(
                pd.to_numeric(
                    providers["rate_limit_count"],
                    errors="coerce",
                ).fillna(0).sum()
            )

    return {
        "success_rate": _pct(
            total_success,
            total_success + total_failure,
        ),
        "refresh_time": f"{avg_latency:.0f} ms",
        "failed_symbols": failed_symbols,
        "queue_size": queue_size,

        "avg_latency_ms": avg_latency,
        "avg_health_score": avg_health,
        "providers_online": providers_online,
        "provider_count": provider_count,
        "rate_limits": rate_limits,

        "providers": providers,
    }


def get_analytics_fabric_metrics(
    db: Session,
    user: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not _has_table(db, "jobs"):
        return {
            "scheduler": "UNKNOWN",
            "queue_depth": 0,
            "running_jobs": 0,
            "jobs_today": 0,
            "failures_today": 0,
            "recovery_actions": 0,
        }

    jobs_today = int(
        _scalar(
            db,
            """
            SELECT COUNT(*)
            FROM jobs
            WHERE created_at::timestamp >= NOW() - INTERVAL '24 hours'
            """,
            0,
        )
        or 0
    )

    failures_today = int(
        _scalar(
            db,
            """
            SELECT COUNT(*)
            FROM jobs
            WHERE status IN ('failed', 'error')
              AND created_at::timestamp >= NOW() - INTERVAL '24 hours'
            """,
            0,
        )
        or 0
    )

    running = int(
        _scalar(
            db,
            "SELECT COUNT(*) FROM jobs WHERE status = 'running'",
            0,
        )
        or 0
    )

    queued = int(
        _scalar(
            db,
            "SELECT COUNT(*) FROM jobs WHERE status = 'queued'",
            0,
        )
        or 0
    )

    return {
        "scheduler": "RUNNING",
        "queue_depth": queued,
        "running_jobs": running,
        "jobs_today": jobs_today,
        "failures_today": failures_today,
        "recovery_actions": 0,
    }


def get_portfolio_metrics(
    db: Session,
    user: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    is_super_admin, tenant_id = _tenant_scope(user)
    scoped_tenant = None if is_super_admin else tenant_id

    total = _count_table(db, "portfolios", scoped_tenant)
    positions = _count_table(db, "portfolio_positions", scoped_tenant)

    return {
        "portfolios": total,
        "positions": positions,
        "avg_return": 0.0,
        "avg_risk": 0.0,
        "sharpe": 0.0,
    }


def get_risk_metrics(
    db: Session,
    user: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not _has_table(db, "analytics_snapshots"):
        return {
            "market_risk": 0.0,
            "risk_label": "UNKNOWN",
            "volatility": 0.0,
            "liquidity": 0.0,
            "concentration": 0.0,
        }

    tenant_clause, params = _analytics_tenant_clause(user)

    avg_risk = float(
        _scalar(
            db,
            f"""
            SELECT AVG(risk_score)
            FROM analytics_snapshots
            WHERE risk_score IS NOT NULL {tenant_clause}
            """,
            0,
            params,
        )
        or 0
    )

    market_risk = round(max(0, 100 - avg_risk), 1) if avg_risk else 0.0
    label = "LOW" if market_risk < 35 else "MEDIUM" if market_risk < 65 else "HIGH"

    return {
        "market_risk": market_risk,
        "risk_label": label,
        "volatility": market_risk,
        "liquidity": max(0, round(market_risk * 0.65, 1)),
        "concentration": max(0, round(market_risk * 0.45, 1)),
    }


def get_top_opportunities(
    db: Session,
    user: Optional[Dict[str, Any]] = None,
    limit: int = 10,
) -> pd.DataFrame:
    expected = [
        "Rank",
        "Symbol",
        "Sector",
        "Score",
        "Rating",
        "Confidence",
    ]

    if not _has_table(db, "analytics_snapshots"):
        return pd.DataFrame(columns=expected)

    tenant_clause, params = _analytics_tenant_clause(user)

    df = _read_sql(
        db,
        f"""
        SELECT symbol AS "Symbol",
               COALESCE(sector, 'Unknown') AS "Sector",
               ROUND(composite_score::numeric, 1) AS "Score",
               COALESCE(rating, signal, 'N/A') AS "Rating",
               ROUND(confidence_score::numeric, 1) AS "Confidence",
               asof AS "AsOf"
        FROM analytics_snapshots
        WHERE composite_score IS NOT NULL {tenant_clause}
        ORDER BY composite_score DESC,
                 confidence_score DESC NULLS LAST,
                 asof DESC
        LIMIT :limit
        """,
        {**params, "limit": limit},
    )

    if df.empty:
        return pd.DataFrame(columns=expected)

    # SQLAlchemy/Postgres may preserve quoted case, but some paths return
    # lowercase mapping keys. Normalize both cases safely.
    df = df.rename(
        columns={
            "symbol": "Symbol",
            "sector": "Sector",
            "score": "Score",
            "rating": "Rating",
            "confidence": "Confidence",
            "asof": "AsOf",
            "Symbol": "Symbol",
            "Sector": "Sector",
            "Score": "Score",
            "Rating": "Rating",
            "Confidence": "Confidence",
            "AsOf": "AsOf",
        }
    )

    for col in expected[1:]:
        if col not in df.columns:
            df[col] = "N/A"

    df["Score"] = pd.to_numeric(df["Score"], errors="coerce").fillna(0).round(1)
    df["Confidence"] = pd.to_numeric(df["Confidence"], errors="coerce").fillna(0).round(1)

    if "Rank" not in df.columns:
        df.insert(0, "Rank", range(1, len(df) + 1))
    return df[expected]


def get_sector_leadership(
    db: Session,
    user: Optional[Dict[str, Any]] = None,
    limit: int = 10,
) -> pd.DataFrame:
    if not _has_table(db, "analytics_snapshots"):
        return pd.DataFrame(columns=["Sector", "Symbols", "AI Score", "Momentum", "Risk"])

    tenant_clause, params = _analytics_tenant_clause(user)

    df = _read_sql(
        db,
        f"""
        SELECT COALESCE(sector, 'Unknown') AS sector,
               COUNT(*) AS symbols,
               ROUND(AVG(composite_score)::numeric, 1) AS ai_score,
               ROUND(AVG(momentum_score)::numeric, 1) AS momentum,
               ROUND(AVG(risk_score)::numeric, 1) AS risk
        FROM analytics_snapshots
        WHERE composite_score IS NOT NULL
          AND sector IS NOT NULL
          AND sector NOT IN ('', 'Unknown')
          {tenant_clause}
        GROUP BY sector
        ORDER BY AVG(composite_score) DESC
        LIMIT :limit
        """,
        {**params, "limit": limit},
    )

    if df.empty:
        return pd.DataFrame(columns=["Sector", "Symbols", "AI Score", "Momentum", "Risk"])

    df.columns = ["Sector", "Symbols", "AI Score", "Momentum", "Risk"]
    return df


def get_earnings_intelligence(
    db: Session,
    user: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Earnings dashboard section.

    Uses earnings_events when present. If the app has not populated an
    earnings table yet, this returns a safe, useful analytics-derived
    watchlist instead of leaving the section visually dead.
    """
    tenant_clause, params = _analytics_tenant_clause(user)
    tenant_id = None

    if user:
        tenant_id = user.get("tenant_id")

    params = {}

    analytics_filter = ""

    if tenant_id:
        analytics_filter = """
            AND a.tenant_id = :tenant_id
        """
        params["tenant_id"] = tenant_id

    empty_table = pd.DataFrame(
        columns=[
            "Symbol",
            "Event Date",
            "Estimate EPS",
            "Actual EPS",
            "AI Score",
            "Rating",
        ]
    )

    if _has_table(db, "earnings_events"):
        upcoming = _read_sql(
            db,
            f"""
            SELECT e.symbol,
                   e.earnings_date,
                   e.eps_estimate,
                   e.eps_actual,
                   a.composite_score,
                   COALESCE(a.rating, a.signal, 'N/A') AS rating
            FROM earnings_events e
            LEFT JOIN LATERAL (
                SELECT symbol,
                       composite_score,
                       rating,
                       signal,
                       asof
                FROM analytics_snapshots a
                WHERE a.symbol = e.symbol
                  {analytics_filter}
                ORDER BY a.asof DESC
                LIMIT 1
            ) a ON TRUE
            WHERE e.earnings_date >= CURRENT_DATE
              AND e.earnings_date < CURRENT_DATE + INTERVAL '7 days'
            ORDER BY e.earnings_date ASC
            LIMIT 25
            """,
            params,
        )

        if not upcoming.empty:
            upcoming = upcoming.rename(
                columns={
                    "symbol": "Symbol",
                    "earnings_date": "Event Date",
                    "eps_estimate": "Estimate EPS",
                    "eps_actual": "Actual EPS",
                    "composite_score": "AI Score",
                    "rating": "Rating",
                }
            )

            score = pd.to_numeric(
                upcoming.get("AI Score"),
                errors="coerce",
            ).fillna(0)

            rating = upcoming.get("Rating", pd.Series(dtype=str)).astype(str)

            high_conviction = int((score >= 70).sum())
            expected_beats = int(
                (
                    (score >= 65)
                    | rating.str.contains("Buy", case=False, na=False)
                ).sum()
            )
            expected_misses = int(
                (
                    (score <= 40)
                    | rating.str.contains("Sell", case=False, na=False)
                ).sum()
            )

            return {
                "next_7_days": len(upcoming),
                "high_conviction": high_conviction,
                "expected_beats": expected_beats,
                "expected_misses": expected_misses,
                "table": upcoming[
                    [
                        "Symbol",
                        "Event Date",
                        "Estimate EPS",
                        "Actual EPS",
                        "AI Score",
                        "Rating",
                    ]
                ],
            }

    # Fallback: no earnings table/data yet.
    # Show high-conviction symbols that should be watched during earnings season.
    if _has_table(db, "analytics_snapshots"):
        watch = _read_sql(
            db,
            f"""
            SELECT symbol,
                   COALESCE(sector, 'Unknown') AS sector,
                   ROUND(composite_score::numeric, 1) AS ai_score,
                   COALESCE(rating, signal, 'N/A') AS rating,
                   ROUND(confidence_score::numeric, 1) AS confidence,
                   asof
            FROM analytics_snapshots
            WHERE composite_score IS NOT NULL
              {tenant_clause}
            ORDER BY composite_score DESC,
                     confidence_score DESC NULLS LAST,
                     asof DESC
            LIMIT 10
            """,
            params,
        )

        if not watch.empty:
            watch = watch.rename(
                columns={
                    "symbol": "Symbol",
                    "sector": "Sector",
                    "ai_score": "AI Score",
                    "rating": "Rating",
                    "confidence": "Confidence",
                    "asof": "Latest Analytics",
                }
            )

            score = pd.to_numeric(
                watch.get("AI Score"),
                errors="coerce",
            ).fillna(0)

            rating = watch.get("Rating", pd.Series(dtype=str)).astype(str)

            return {
                "next_7_days": 0,
                "high_conviction": int((score >= 70).sum()),
                "expected_beats": int(
                    (
                        (score >= 65)
                        | rating.str.contains("Buy", case=False, na=False)
                    ).sum()
                ),
                "expected_misses": int(
                    (
                        (score <= 40)
                        | rating.str.contains("Sell", case=False, na=False)
                    ).sum()
                ),
                "table": watch[
                    [
                        "Symbol",
                        "Sector",
                        "AI Score",
                        "Rating",
                        "Confidence",
                        "Latest Analytics",
                    ]
                ],
            }

    return {
        "next_7_days": 0,
        "high_conviction": 0,
        "expected_beats": 0,
        "expected_misses": 0,
        "table": empty_table,
    }


def get_smart_money_metrics(
    db: Session,
    user: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Live Smart Money dashboard section.

    Sources:
    - insider_transactions
    - sec_form4_filings
    - smart_money_signals
    - institutional_holdings

    Notes:
    - The function is schema-aware and checks columns before referencing them.
    - Counts use the full tables.
    - Dataframes are limited for UI display only.
    """
    tenant_clause, params = _analytics_tenant_clause(user)

    insider_buys = 0
    insider_sells = 0
    insider_rows_total = 0
    form4_filings = 0
    form4_rows_total = 0
    institutional_rows_total = 0
    institutional_accumulation = 0
    institutional_distribution = 0
    signal_rows_total = 0
    signal_leaders = 0
    avg_smart_money_score = 0.0
    top_smart_money_symbol = "N/A"

    leaders = pd.DataFrame(
        columns=[
            "Symbol",
            "Smart Money Score",
            "Accumulation",
            "Distribution",
            "Insider",
            "Institutional",
            "Options",
        ]
    )
    insider_table = pd.DataFrame()
    institutional_table = pd.DataFrame()
    form4_table = pd.DataFrame()

    # ---------------------------------------------------------
    # Insider transactions
    # ---------------------------------------------------------
    if _has_table(db, "insider_transactions"):
        insider_rows_total = _count_table(db, "insider_transactions")

        type_col = None
        for candidate in ["transaction_type", "transaction_code", "type", "action"]:
            if _has_column(db, "insider_transactions", candidate):
                type_col = candidate
                break

        date_col = None
        for candidate in ["transaction_date", "filing_date", "created_at", "asof"]:
            if _has_column(db, "insider_transactions", candidate):
                date_col = candidate
                break

        symbol_col = "symbol" if _has_column(db, "insider_transactions", "symbol") else None

        value_col = None
        for candidate in ["value", "transaction_value", "market_value", "amount"]:
            if _has_column(db, "insider_transactions", candidate):
                value_col = candidate
                break

        shares_col = None
        for candidate in ["shares", "share_count", "quantity"]:
            if _has_column(db, "insider_transactions", candidate):
                shares_col = candidate
                break

        insider_name_col = None
        for candidate in ["insider_name", "owner_name", "reporting_owner", "name"]:
            if _has_column(db, "insider_transactions", candidate):
                insider_name_col = candidate
                break

        title_col = "title" if _has_column(db, "insider_transactions", "title") else None

        if type_col:
            date_filter = (
                f" AND {date_col} >= CURRENT_DATE - INTERVAL '180 days' "
                if date_col
                else ""
            )

            insider_buys = int(
                _scalar(
                    db,
                    f"""
                    SELECT COUNT(*)
                    FROM insider_transactions
                    WHERE UPPER(COALESCE({type_col}::text, '')) IN
                          ('BUY', 'PURCHASE', 'P', 'ACQUIRE', 'ACQUIRED')
                    {date_filter}
                    """,
                    0,
                )
                or 0
            )

            insider_sells = int(
                _scalar(
                    db,
                    f"""
                    SELECT COUNT(*)
                    FROM insider_transactions
                    WHERE UPPER(COALESCE({type_col}::text, '')) IN
                          ('SELL', 'SALE', 'S', 'DISPOSE', 'DISPOSED')
                    {date_filter}
                    """,
                    0,
                )
                or 0
            )

        select_cols = []
        if date_col:
            select_cols.append(f"{date_col} AS \"Date\"")
        if insider_name_col:
            select_cols.append(f"{insider_name_col} AS \"Insider\"")
        if title_col:
            select_cols.append(f"{title_col} AS \"Title\"")
        if shares_col:
            select_cols.append(f"{shares_col} AS \"Shares\"")
        if value_col:
            select_cols.append(f"{value_col} AS \"Value\"")
        if type_col:
            select_cols.append(f"{type_col} AS \"Transaction\"")
        if symbol_col:
            select_cols.append(f"{symbol_col} AS \"Symbol\"")

        if select_cols:
            order_col = date_col or "1"
            insider_table = _read_sql(
                db,
                f"""
                SELECT {", ".join(select_cols)}
                FROM insider_transactions
                ORDER BY {order_col} DESC NULLS LAST
                LIMIT 25
                """,
            )

    # ---------------------------------------------------------
    # SEC Form 4 filings
    # ---------------------------------------------------------
    if _has_table(db, "sec_form4_filings"):
        form4_filings = _count_table(db, "sec_form4_filings")
        form4_rows_total = form4_filings

        form4_cols = []
        for col, label in [
            ("filing_date", "Filing Date"),
            ("symbol", "Symbol"),
            ("filing_type", "Type"),
            ("cik", "CIK"),
            ("accession_number", "Accession"),
            ("transaction_date", "Transaction Date"),
            ("filing_url", "URL"),
            ("parsed", "Parsed"),
        ]:
            if _has_column(db, "sec_form4_filings", col):
                form4_cols.append(f"{col} AS \"{label}\"")

        if form4_cols:
            order_col = "filing_date" if _has_column(db, "sec_form4_filings", "filing_date") else "1"
            form4_table = _read_sql(
                db,
                f"""
                SELECT {", ".join(form4_cols)}
                FROM sec_form4_filings
                ORDER BY {order_col} DESC NULLS LAST
                LIMIT 25
                """,
            )

    # ---------------------------------------------------------
    # Institutional holdings
    # ---------------------------------------------------------
    if _has_table(db, "institutional_holdings"):
        institutional_rows_total = _count_table(db, "institutional_holdings")

        if _has_column(db, "institutional_holdings", "change_pct"):
            institutional_accumulation = int(
                _scalar(
                    db,
                    """
                    SELECT COUNT(DISTINCT symbol)
                    FROM institutional_holdings
                    WHERE COALESCE(change_pct, 0) > 0
                    """,
                    0,
                )
                or 0
            )

            institutional_distribution = int(
                _scalar(
                    db,
                    """
                    SELECT COUNT(DISTINCT symbol)
                    FROM institutional_holdings
                    WHERE COALESCE(change_pct, 0) < 0
                    """,
                    0,
                )
                or 0
            )

        inst_cols = []
        if _has_column(db, "institutional_holdings", "symbol"):
            inst_cols.append("symbol AS \"Symbol\"")

        if _has_column(db, "institutional_holdings", "institution") and _has_column(db, "institutional_holdings", "fund_name"):
            inst_cols.append("COALESCE(institution, fund_name) AS \"Institution\"")
        elif _has_column(db, "institutional_holdings", "institution"):
            inst_cols.append("institution AS \"Institution\"")
        elif _has_column(db, "institutional_holdings", "fund_name"):
            inst_cols.append("fund_name AS \"Institution\"")

        for col, label in [
            ("shares", "Shares"),
            ("previous_shares", "Previous Shares"),
            ("market_value", "Market Value"),
            ("ownership_pct", "Ownership %"),
            ("change_pct", "Change %"),
            ("filing_date", "Filing Date"),
            ("report_period", "Report Period"),
            ("source", "Source"),
        ]:
            if _has_column(db, "institutional_holdings", col):
                inst_cols.append(f"{col} AS \"{label}\"")

        if inst_cols:
            order_col = (
                "ABS(COALESCE(change_pct, 0))"
                if _has_column(db, "institutional_holdings", "change_pct")
                else "1"
            )
            institutional_table = _read_sql(
                db,
                f"""
                SELECT {", ".join(inst_cols)}
                FROM institutional_holdings
                ORDER BY {order_col} DESC NULLS LAST
                LIMIT 25
                """,
            )

    # ---------------------------------------------------------
    # Smart money signal table
    # ---------------------------------------------------------
    if _has_table(db, "smart_money_signals"):
        signal_rows_total = _count_table(db, "smart_money_signals")

        if _has_column(db, "smart_money_signals", "smart_money_score"):
            signal_leaders = int(
                _scalar(
                    db,
                    """
                    SELECT COUNT(*)
                    FROM smart_money_signals
                    WHERE COALESCE(smart_money_score, 0) >= 70
                    """,
                    0,
                )
                or 0
            )

            avg_smart_money_score = float(
                _scalar(
                    db,
                    """
                    SELECT ROUND(AVG(smart_money_score)::numeric, 1)
                    FROM smart_money_signals
                    WHERE smart_money_score IS NOT NULL
                    """,
                    0,
                )
                or 0
            )

            top_symbol = _scalar(
                db,
                """
                SELECT symbol
                FROM smart_money_signals
                ORDER BY smart_money_score DESC NULLS LAST,
                         created_at DESC NULLS LAST
                LIMIT 1
                """,
                "N/A",
            )
            if top_symbol:
                top_smart_money_symbol = str(top_symbol)

        if _has_column(db, "smart_money_signals", "accumulation_score"):
            institutional_accumulation = max(
                institutional_accumulation,
                int(
                    _scalar(
                        db,
                        """
                        SELECT COUNT(DISTINCT symbol)
                        FROM smart_money_signals
                        WHERE COALESCE(accumulation_score, 0) >= 65
                        """,
                        0,
                    )
                    or 0
                ),
            )

        if _has_column(db, "smart_money_signals", "distribution_score"):
            institutional_distribution = max(
                institutional_distribution,
                int(
                    _scalar(
                        db,
                        """
                        SELECT COUNT(DISTINCT symbol)
                        FROM smart_money_signals
                        WHERE COALESCE(distribution_score, 0) >= 65
                        """,
                        0,
                    )
                    or 0
                ),
            )

        signal_cols = []
        for col, label in [
            ("symbol", "Symbol"),
            ("smart_money_score", "Smart Money Score"),
            ("accumulation_score", "Accumulation"),
            ("distribution_score", "Distribution"),
            ("insider_score", "Insider"),
            ("institutional_score", "Institutional"),
            ("form4_score", "Form 4"),
            ("options_score", "Options"),
            ("ai_score", "AI"),
            ("confidence_score", "Confidence"),
            ("signal", "Signal"),
            ("created_at", "Created"),
        ]:
            if _has_column(db, "smart_money_signals", col):
                signal_cols.append(f"{col} AS \"{label}\"")

        if signal_cols:
            order_col = (
                "smart_money_score"
                if _has_column(db, "smart_money_signals", "smart_money_score")
                else "created_at"
            )
            leaders = _read_sql(
                db,
                f"""
                SELECT {", ".join(signal_cols)}
                FROM smart_money_signals
                ORDER BY {order_col} DESC NULLS LAST
                LIMIT 25
                """,
            )

    # ---------------------------------------------------------
    # Analytics-derived fallback when signal table has no rows.
    # ---------------------------------------------------------
    if leaders.empty and _has_table(db, "analytics_snapshots"):
        analytics = _read_sql(
            db,
            f"""
            SELECT symbol,
                   COALESCE(rating, signal, 'N/A') AS signal,
                   COALESCE(composite_score, 0) AS composite_score,
                   COALESCE(momentum_score, 0) AS momentum_score,
                   COALESCE(risk_score, 0) AS risk_score,
                   COALESCE(latest_volume, 0) AS latest_volume,
                   COALESCE(confidence_score, 0) AS confidence_score,
                   asof
            FROM analytics_snapshots
            WHERE composite_score IS NOT NULL
              {tenant_clause}
            ORDER BY asof DESC
            """,
            params,
        )

        if not analytics.empty:
            for col in [
                "composite_score",
                "momentum_score",
                "risk_score",
                "latest_volume",
                "confidence_score",
            ]:
                analytics[col] = pd.to_numeric(
                    analytics.get(col),
                    errors="coerce",
                ).fillna(0)

            max_volume = float(analytics["latest_volume"].max() or 0)
            analytics["volume_score"] = (
                (analytics["latest_volume"] / max_volume * 100).clip(0, 100)
                if max_volume > 0
                else 0.0
            )

            analytics["smart_money_score"] = (
                analytics["composite_score"] * 0.35
                + analytics["momentum_score"] * 0.25
                + analytics["volume_score"] * 0.20
                + analytics["risk_score"] * 0.10
                + analytics["confidence_score"] * 0.10
            ).clip(0, 100)

            signals = analytics.get("signal", pd.Series(dtype=str)).astype(str)

            derived_accumulation = analytics[
                (
                    (analytics["smart_money_score"] >= 65)
                    | (
                        signals.str.contains("Buy", case=False, na=False)
                        & (analytics["momentum_score"] >= 55)
                    )
                )
            ]

            derived_distribution = analytics[
                (
                    (analytics["smart_money_score"] <= 40)
                    | signals.str.contains("Sell", case=False, na=False)
                )
            ]

            institutional_accumulation = max(
                institutional_accumulation,
                int(len(derived_accumulation)),
            )
            institutional_distribution = max(
                institutional_distribution,
                int(len(derived_distribution)),
            )

            signal_rows_total = int(len(analytics))
            signal_leaders = int((analytics["smart_money_score"] >= 70).sum())
            avg_smart_money_score = float(analytics["smart_money_score"].mean() or 0)
            top_smart_money_symbol = str(
                analytics.sort_values(
                    ["smart_money_score", "composite_score"],
                    ascending=[False, False],
                )
                .iloc[0]
                .get("symbol", "N/A")
            )

            leaders = (
                analytics.sort_values(
                    ["smart_money_score", "composite_score"],
                    ascending=[False, False],
                )
                .head(25)
                .rename(
                    columns={
                        "symbol": "Symbol",
                        "signal": "Signal",
                        "smart_money_score": "Smart Money Score",
                        "composite_score": "AI Score",
                        "momentum_score": "Momentum",
                        "volume_score": "Volume",
                        "risk_score": "Risk",
                    }
                )
            )

            leaders = leaders[
                [
                    "Symbol",
                    "Signal",
                    "Smart Money Score",
                    "AI Score",
                    "Momentum",
                    "Volume",
                    "Risk",
                ]
            ]

    for frame in [leaders, insider_table, institutional_table, form4_table]:
        if frame is not None and not frame.empty:
            for col in frame.columns:
                if any(
                    token in col.lower()
                    for token in [
                        "score",
                        "accumulation",
                        "distribution",
                        "insider",
                        "institutional",
                        "options",
                        "ai",
                        "momentum",
                        "volume",
                        "risk",
                        "change",
                        "ownership",
                        "shares",
                        "value",
                        "market",
                        "confidence",
                    ]
                ):
                    try:
                        frame[col] = pd.to_numeric(frame[col], errors="coerce")
                        if pd.api.types.is_numeric_dtype(frame[col]):
                            frame[col] = frame[col].round(1)
                    except Exception:
                        pass

    return {
        "insider_buys": insider_buys,
        "insider_sells": insider_sells,
        "insider_rows": insider_rows_total,
        "form4_filings": form4_filings,
        "form4_rows": form4_rows_total,
        "institutional_accumulation": institutional_accumulation,
        "institutional_distribution": institutional_distribution,
        "institutional_rows": institutional_rows_total,
        "signal_rows": signal_rows_total,
        "signal_leaders": signal_leaders,
        "avg_smart_money_score": round(avg_smart_money_score, 1),
        "top_smart_money_symbol": top_smart_money_symbol,
        "leaders": leaders,
        "insider_table": insider_table,
        "institutional_table": institutional_table,
        "form4_table": form4_table,
    }

# -----------------------------------------------------------------------------
# Rendering helpers
# -----------------------------------------------------------------------------


def _metric_row(items: Iterable[tuple[str, Any]], columns: int = 4) -> None:
    cols = st.columns(columns)
    for col, (label, value) in zip(cols, items):
        col.metric(label, value)


def _safe_dataframe(df: pd.DataFrame, height: Optional[int] = None) -> None:
    if df is None or df.empty:
        st.info("No data available yet.")
        return

    display_df = df.copy().reset_index(drop=True)
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        height=height,
    )


def _render_ai_summary(
    market: Dict[str, Any],
    ai: Dict[str, Any],
    universe: Dict[str, Any],
    risk: Dict[str, Any],
) -> None:
    summary = (
        f"**{ai['regime']}** market posture. "
        f"Current breadth is **{market['breadth_pct']:.1f}% advancers**, "
        f"analytics coverage is **{universe['coverage']:.1f}%**, "
        f"top AI pick is **{ai['top_pick']}** with score **{ai['top_score']:.1f}**, "
        f"and market risk is **{risk['risk_label']} ({risk['market_risk']:.1f}/100)**."
    )
    st.info(summary)


# -----------------------------------------------------------------------------
# Main dashboard
# -----------------------------------------------------------------------------


def render_executive_dashboard(
    db: Session,
    user: Optional[Dict[str, Any]] = None,
):
    role = str((user or {}).get("role", "")).lower()
    is_admin = role in {
        "admin",
        "super_admin",
        "superadmin",
        "tenant_admin",
    }

    st.markdown("## Executive Dashboard")

    market = get_market_metrics(db, user)
    universe = get_universe_metrics(db, user)
    ai = get_ai_metrics(db, user)
    platform = get_platform_metrics(db, user)
    provider = get_provider_metrics(db)
    fabric = get_analytics_fabric_metrics(db, user)
    portfolio = get_portfolio_metrics(db, user)
    risk = get_risk_metrics(db, user)
    earnings = get_earnings_intelligence(db, user)
    smart_money = get_smart_money_metrics(db, user)

    _render_ai_summary(market, ai, universe, risk)

    st.divider()

    st.markdown("### Market Intelligence Command Center")
    _metric_row(
        [
            ("Market Regime", ai["regime"]),
            ("Breadth", _fmt_pct(market["breadth_pct"])),
            ("Advancers", _fmt_number(market["advancers"])),
            ("Decliners", _fmt_number(market["decliners"])),
        ],
        4,
    )

    st.divider()

    st.markdown("### Research Universe Intelligence")
    _metric_row(
        [
            ("Tracked Securities", _fmt_number(universe["tracked"])),
            ("Analyzed", _fmt_number(universe["analyzed"])),
            ("Coverage", _fmt_pct(universe["coverage"])),
            ("Missing Data", _fmt_number(universe["missing"])),
        ],
        4,
    )
    _metric_row(
        [
            ("Updated Today", _fmt_number(universe["updated_today"])),
            ("Latest Snapshot", str(universe["latest_snapshot"] or "N/A")[:19]),
            ("Queue Depth", _fmt_number(provider["queue_size"])),
            ("Failed Symbols", _fmt_number(provider["failed_symbols"])),
        ],
        4,
    )

    st.divider()

    st.markdown("### AI Intelligence")
    _metric_row(
        [
            ("Top AI Pick", ai["top_pick"]),
            ("Top Score", f"{ai['top_score']:.1f}"),
            ("Top Sector", ai["top_sector"]),
            ("Confidence", _fmt_pct(ai["confidence"])),
        ],
        4,
    )

    st.markdown("#### Highest Conviction Opportunities")
    _safe_dataframe(get_top_opportunities(db, user, 10), height=390)

    st.divider()

    st.markdown("### Sector Leadership")
    _safe_dataframe(get_sector_leadership(db, user, 12), height=390)

    st.divider()

    st.markdown("### Portfolio Command Center")
    _metric_row(
        [
            ("Portfolios", _fmt_number(portfolio["portfolios"])),
            ("Positions", _fmt_number(portfolio["positions"])),
            ("Avg Return", _fmt_pct(portfolio["avg_return"])),
            ("Sharpe", f"{portfolio['sharpe']:.2f}"),
        ],
        4,
    )

    st.divider()

    st.markdown("### AI Research Factory")
    _metric_row(
        [
            ("Analytics Snapshots", _fmt_number(universe["analyzed"])),
            ("Fresh Today", _fmt_number(universe["updated_today"])),
            ("Coverage", _fmt_pct(universe["coverage"])),
            ("Missing", _fmt_number(universe["missing"])),
        ],
        4,
    )

    st.divider()

    st.markdown("### Earnings Intelligence")
    _metric_row(
        [
            ("Next 7 Days", _fmt_number(earnings["next_7_days"])),
            ("High Conviction", _fmt_number(earnings["high_conviction"])),
            ("Expected Beats", _fmt_number(earnings["expected_beats"])),
            ("Expected Misses", _fmt_number(earnings["expected_misses"])),
        ],
        4,
    )

    if not earnings["table"].empty:
        _safe_dataframe(earnings["table"], height=300)

    st.divider()

    st.markdown("### Smart Money Tracker")
    _metric_row(
        [
            ("Top SM Symbol", smart_money.get("top_smart_money_symbol", "N/A")),
            ("Avg SM Score", f"{float(smart_money.get('avg_smart_money_score', 0) or 0):.1f}"),
            ("Signal Leaders", _fmt_number(smart_money.get("signal_leaders", 0))),
            ("Signal Rows", _fmt_number(smart_money.get("signal_rows", 0))),
        ],
        4,
    )
    _metric_row(
        [
            ("Insider Buys", _fmt_number(smart_money["insider_buys"])),
            ("Insider Sells", _fmt_number(smart_money["insider_sells"])),
            ("Insider Rows", _fmt_number(smart_money.get("insider_rows", 0))),
            ("Form 4 Filings", _fmt_number(smart_money.get("form4_filings", 0))),
        ],
        4,
    )
    _metric_row(
        [
            (
                "Institutional Accumulation",
                _fmt_number(smart_money["institutional_accumulation"]),
            ),
            (
                "Institutional Distribution",
                _fmt_number(smart_money["institutional_distribution"]),
            ),
            ("Institutional Rows", _fmt_number(smart_money.get("institutional_rows", 0))),
            ("Form 4 Rows", _fmt_number(smart_money.get("form4_rows", 0))),
        ],
        4,
    )

    tab_sm_leaders, tab_sm_insiders, tab_sm_inst, tab_sm_form4 = st.tabs(
        [
            "Smart Money Leaders",
            "Insider Transactions",
            "Institutional Holdings",
            "SEC Form 4",
        ]
    )

    with tab_sm_leaders:
        _safe_dataframe(smart_money.get("leaders"), height=360)

    with tab_sm_insiders:
        _safe_dataframe(smart_money.get("insider_table"), height=360)

    with tab_sm_inst:
        _safe_dataframe(smart_money.get("institutional_table"), height=360)

    with tab_sm_form4:
        _safe_dataframe(smart_money.get("form4_table"), height=360)

    st.divider()

    st.markdown("### Risk Center")
    _metric_row(
        [
            ("Market Risk", f"{risk['market_risk']:.1f}/100"),
            ("Risk State", risk["risk_label"]),
            ("Volatility Risk", f"{risk['volatility']:.1f}"),
            ("Liquidity Risk", f"{risk['liquidity']:.1f}"),
        ],
        4,
    )

    st.divider()

    st.markdown("### Analytics Fabric Status")
    _metric_row(
        [
            ("Scheduler", fabric["scheduler"]),
            ("Queue Depth", _fmt_number(fabric["queue_depth"])),
            ("Running Jobs", _fmt_number(fabric["running_jobs"])),
            ("Jobs Today", _fmt_number(fabric["jobs_today"])),
        ],
        4,
    )
    _metric_row(
        [
            ("Failures Today", _fmt_number(fabric["failures_today"])),
            ("Recovery Actions", _fmt_number(fabric["recovery_actions"])),
            ("Provider Success", _fmt_pct(provider["success_rate"])),
            ("Refresh Time", provider["refresh_time"]),
        ],
        4,
    )

    st.divider()

    st.markdown("### Data Provider Operations Center")

    _metric_row(
        [
            (
                "Success Rate",
                _fmt_pct(provider["success_rate"])
            ),
            (
                "Avg Health",
                f"{provider.get('avg_health_score', 0):.1f}%"
            ),
            (
                "Providers Online",
                f"{provider.get('providers_online', 0)}/"
                f"{provider.get('provider_count', 0)}"
            ),
            (
                "Avg Latency",
                f"{provider.get('avg_latency_ms', 0):.0f} ms"
            ),
            (
                "Rate Limits",
                _fmt_number(
                    provider.get("rate_limits", 0)
                )
            ),
            (
                "Failed Symbols",
                _fmt_number(
                    provider["failed_symbols"]
                )
            ),
            (
                "Queue Size",
                _fmt_number(
                    provider["queue_size"]
                )
            ),
        ],
        7,
    )

    if not provider["providers"].empty:
        display_df = provider["providers"].copy()

        display_df = display_df.rename(
            columns={
                "provider": "Provider",
                "health_score": "Health",
                "success_count": "Success",
                "failure_count": "Failures",
                "rate_limit_count": "Rate Limits",
                "avg_latency_ms": "Latency (ms)",
                "cooldown_until": "Cooldown Until",
                "last_success": "Last Success",
                "last_failure": "Last Failure",
                "updated_at": "Last Update",
            }
        )

        _safe_dataframe(
            display_df,
            height=320,
        )



    if is_admin:
        st.divider()
        st.markdown("### Platform Activity")
        _metric_row(
            [
                ("Watchlists", _fmt_number(platform["watchlists"])),
                ("Portfolios", _fmt_number(platform["portfolios"])),
                ("Alerts", _fmt_number(platform["alerts"])),
                ("Reports", _fmt_number(platform["reports"])),
            ],
            4,
        )
        _metric_row(
            [
                ("Users", _fmt_number(platform["users"])),
                ("Tenants", _fmt_number(platform["tenants"])),
                ("Database", "Online"),
                ("Auth", "Active"),
            ],
            4,
        )

    st.caption(
        f"Dashboard updated {datetime.now(UTC):%Y-%m-%d %H:%M:%S UTC}"
    )
