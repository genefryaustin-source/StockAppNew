import sqlite3

OLD_DB = "old_stockapp.db"
NEW_DB = "new_stockapp.db"

conn_old = sqlite3.connect(OLD_DB)
conn_new = sqlite3.connect(NEW_DB)

cur_old = conn_old.cursor()
cur_new = conn_new.cursor()

tables = [
    "alert_events",
    "analytics_snapshots",
    "closed_trades",
    "discovered_strategies",
    "earnings_events",
    "factor_store",
    "financial_periods",
    "fundamental_snapshots",
    "jobs",
    "market_data_cache",
    "portfolio_cash_ledger",
    "portfolio_daily_pnl",
    "portfolio_positions",
    "portfolio_snapshots",
    "portfolio_trades",
    "portfolios",
    "positions",
    "price_history",
    "security_master",
    "strategy_runs",
    "tenants",
    "trade_fills",
    "trade_orders",
    "universe_analytics_cache",
    "universe_equities",
    "universe_symbols",
    "universes",
    "users",
    "watchlist_items",
]

def migrate_table(table):
    try:
        print(f"\n--- Migrating {table} ---")

        rows = cur_old.execute(f"SELECT * FROM {table}").fetchall()

        if not rows:
            print("No data")
            return

        cols = [desc[0] for desc in cur_old.description]
        col_str = ",".join(cols)

        placeholders = ",".join(["?"] * len(cols))

        query = f"""
        INSERT OR IGNORE INTO {table} ({col_str})
        VALUES ({placeholders})
        """

        cur_new.executemany(query, rows)

        print(f"✔ {len(rows)} rows migrated")

    except Exception as e:
        print(f"❌ ERROR in {table}: {e}")


for t in tables:
    migrate_table(t)

conn_new.commit()

conn_old.close()
conn_new.close()

print("\n🔥 MIGRATION COMPLETE")