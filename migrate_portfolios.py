import sqlite3

DB = "stockapp.db"

conn = sqlite3.connect(DB)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS portfolios (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    name TEXT NOT NULL,
    created_at DATETIME
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS portfolio_positions (
    id TEXT PRIMARY KEY,
    portfolio_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    quantity REAL NOT NULL,
    cost_basis REAL NOT NULL,
    created_at DATETIME
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS portfolio_trades (
    id TEXT PRIMARY KEY,
    portfolio_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity REAL NOT NULL,
    price REAL NOT NULL,
    trade_date DATETIME
)
""")

cur.execute("""
CREATE INDEX IF NOT EXISTS idx_portfolio_positions
ON portfolio_positions(portfolio_id, symbol)
""")

conn.commit()
conn.close()

print("Portfolio tables created")