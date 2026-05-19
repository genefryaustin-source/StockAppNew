import sqlite3

DB_FILE = "stockapp.db"


def table_exists(cursor, table):
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    )
    return cursor.fetchone() is not None


def column_exists(cursor, table, column):
    cursor.execute(f"PRAGMA table_info({table})")
    cols = [row[1] for row in cursor.fetchall()]
    return column in cols


def add_column(cursor, table, column, definition):
    if not table_exists(cursor, table):
        print(f"SKIP {table}.{column} (table missing)")
        return

    if not column_exists(cursor, table, column):
        print(f"Adding {table}.{column}")
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
    else:
        print(f"OK {table}.{column}")


def create_indexes(cursor):
    stmts = [
        "CREATE INDEX IF NOT EXISTS idx_analytics_tenant_symbol_asof ON analytics_snapshots(tenant_id, symbol, asof)",
        "CREATE INDEX IF NOT EXISTS idx_earnings_tenant_symbol_event_date ON earnings_events(tenant_id, symbol, event_date)",
        "CREATE INDEX IF NOT EXISTS idx_financial_periods_tenant_symbol_period_end ON financial_periods(tenant_id, symbol, period_end)",
        "CREATE INDEX IF NOT EXISTS idx_jobs_tenant_status_created ON jobs(tenant_id, status, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_watchlists_tenant ON watchlists(tenant_id)",
        "CREATE INDEX IF NOT EXISTS idx_watchlist_items_watchlist_symbol ON watchlist_items(watchlist_id, symbol)",
        "CREATE INDEX IF NOT EXISTS idx_universes_tenant ON universes(tenant_id)",
        "CREATE INDEX IF NOT EXISTS idx_universe_symbols_universe_symbol ON universe_symbols(universe_id, symbol)",
    ]
    for stmt in stmts:
        try:
            cursor.execute(stmt)
        except Exception as e:
            print(f"Index warning: {e}")


def repair_analytics_snapshots(cursor):
    cols = {
        "id": "TEXT",
        "tenant_id": "TEXT",
        "symbol": "TEXT",
        "asof": "DATETIME",
        "sector": "TEXT",
        "revenue_cagr_3y": "REAL",
        "gross_margin": "REAL",
        "op_margin": "REAL",
        "fcf_margin": "REAL",
        "pe_ttm": "REAL",
        "ps_ttm": "REAL",
        "ev_ebitda": "REAL",
        "trend": "TEXT",
        "rsi_14": "REAL",
        "sma_50": "REAL",
        "sma_200": "REAL",
        "support": "REAL",
        "resistance": "REAL",
        "vol_20d": "REAL",
        "max_drawdown_1y": "REAL",
        "risk_score": "REAL",
        "rating": "TEXT",
        "rating_rationale": "TEXT",
        "quality_score": "REAL",
        "growth_score": "REAL",
        "value_score": "REAL",
        "momentum_score": "REAL",
        "composite_score": "REAL",
        "confidence_score": "REAL",
    }
    for c, d in cols.items():
        add_column(cursor, "analytics_snapshots", c, d)


def repair_earnings_events(cursor):
    cols = {
        "event_date": "DATETIME",
        "earnings_date": "DATETIME",
        "time_of_day": "TEXT",
        "eps_actual": "REAL",
        "eps_estimate": "REAL",
        "eps_est": "REAL",
        "rev_actual": "REAL",
        "rev_est": "REAL",
        "revenue_actual": "REAL",
        "revenue_estimate": "REAL",
        "rev_estimate": "REAL",
        "source": "TEXT",
        "created_at": "DATETIME",
    }
    for c, d in cols.items():
        add_column(cursor, "earnings_events", c, d)

    # backfill earnings_date from event_date if missing
    if table_exists(cursor, "earnings_events"):
        try:
            cursor.execute("""
                UPDATE earnings_events
                SET earnings_date = event_date
                WHERE earnings_date IS NULL AND event_date IS NOT NULL
            """)
        except Exception as e:
            print(f"Backfill warning earnings_events: {e}")


def repair_financial_periods(cursor):
    cols = {
        "source": "TEXT",
        "ebitda": "REAL",
        "operating_cash_flow": "REAL",
        "capex": "REAL",
        "free_cash_flow": "REAL",
        "cash": "REAL",
        "total_debt": "REAL",
        "created_at": "DATETIME",
    }
    for c, d in cols.items():
        add_column(cursor, "financial_periods", c, d)


def repair_jobs(cursor):
    cols = {
        "universe_id": "TEXT",
        "symbol": "TEXT",
        "total": "INTEGER",
        "done": "INTEGER",
        "payload": "TEXT",
        "logs": "TEXT",
        "error": "TEXT",
        "started_at": "TEXT",
        "finished_at": "TEXT",
    }
    for c, d in cols.items():
        add_column(cursor, "jobs", c, d)


def repair_watchlists(cursor):
    cols_watchlists = {
        "created_by_user_id": "TEXT",
        "created_at": "DATETIME",
    }
    for c, d in cols_watchlists.items():
        add_column(cursor, "watchlists", c, d)

    cols_items = {
        "tenant_id": "TEXT",
        "created_at": "DATETIME",
    }
    for c, d in cols_items.items():
        add_column(cursor, "watchlist_items", c, d)

    # backfill watchlist_items.tenant_id from parent watchlist
    if table_exists(cursor, "watchlist_items") and table_exists(cursor, "watchlists"):
        try:
            cursor.execute("""
                UPDATE watchlist_items
                SET tenant_id = (
                    SELECT watchlists.tenant_id
                    FROM watchlists
                    WHERE watchlists.id = watchlist_items.watchlist_id
                )
                WHERE tenant_id IS NULL
            """)
        except Exception as e:
            print(f"Backfill warning watchlist_items.tenant_id: {e}")

    # backfill created_at
    try:
        cursor.execute("""
            UPDATE watchlists
            SET created_at = CURRENT_TIMESTAMP
            WHERE created_at IS NULL
        """)
    except Exception:
        pass

    try:
        cursor.execute("""
            UPDATE watchlist_items
            SET created_at = CURRENT_TIMESTAMP
            WHERE created_at IS NULL
        """)
    except Exception:
        pass


def repair_universe_tables(cursor):
    cols_universes = {
        "description": "TEXT",
        "created_by_user_id": "TEXT",
        "refresh_hours": "INTEGER DEFAULT 24",
        "created_at": "TEXT",
    }
    for c, d in cols_universes.items():
        add_column(cursor, "universes", c, d)

    cols_universe_symbols = {
        "tenant_id": "TEXT",
        "added_at": "DATETIME",
    }
    for c, d in cols_universe_symbols.items():
        add_column(cursor, "universe_symbols", c, d)

    cols_cache = {
        "analytics_snapshot_id": "TEXT",
        "analytics_asof": "DATETIME",
        "sector": "TEXT",
        "rating": "TEXT",
        "composite_score": "REAL",
        "confidence_score": "REAL",
        "quality": "REAL",
        "growth": "REAL",
        "value": "REAL",
        "momentum": "REAL",
        "risk": "REAL",
        "updated_at": "DATETIME",
    }
    for c, d in cols_cache.items():
        add_column(cursor, "universe_analytics_cache", c, d)


def normalize_analytics_asof(cursor):
    if table_exists(cursor, "analytics_snapshots"):
        try:
            cursor.execute("""
                UPDATE analytics_snapshots
                SET asof = CURRENT_TIMESTAMP
                WHERE asof IS NULL
            """)
        except Exception as e:
            print(f"Backfill warning analytics_snapshots.asof: {e}")


def main():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    print("\n=== Repairing schema ===\n")

    repair_analytics_snapshots(cursor)
    repair_earnings_events(cursor)
    repair_financial_periods(cursor)
    repair_jobs(cursor)
    repair_watchlists(cursor)
    repair_universe_tables(cursor)
    normalize_analytics_asof(cursor)
    create_indexes(cursor)

    conn.commit()
    conn.close()

    print("\n=== Schema repair complete ===\n")


if __name__ == "__main__":
    main()