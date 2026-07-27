"""
modules/forex/forex_terminal_seed_data.py

Optional seed utility for local/paper Forex dashboard validation.
Creates minimal Forex-specific test tables if they do not exist.
"""

from __future__ import annotations
from datetime import datetime, timezone, timedelta

try:
    from sqlalchemy import text
except Exception:
    text = None


def seed_forex_terminal_demo_data(db, tenant_id="demo", user_id="demo", portfolio_id="forex-demo"):
    if db is None or text is None:
        return {"status": "ERROR", "message": "db and sqlalchemy.text are required"}

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    db.execute(text("""
        CREATE TABLE IF NOT EXISTS forex_positions (
            id SERIAL PRIMARY KEY,
            portfolio_id VARCHAR(100),
            symbol VARCHAR(20),
            side VARCHAR(20),
            lots DOUBLE PRECISION,
            entry_price DOUBLE PRECISION,
            current_price DOUBLE PRECISION,
            market_value DOUBLE PRECISION,
            unrealized_pnl DOUBLE PRECISION,
            updated_at TIMESTAMP
        )
    """))

    db.execute(text("""
        CREATE TABLE IF NOT EXISTS forex_orders (
            id SERIAL PRIMARY KEY,
            portfolio_id VARCHAR(100),
            symbol VARCHAR(20),
            side VARCHAR(20),
            order_type VARCHAR(50),
            quantity DOUBLE PRECISION,
            price DOUBLE PRECISION,
            status VARCHAR(50),
            created_at TIMESTAMP
        )
    """))

    db.execute(text("""
        CREATE TABLE IF NOT EXISTS forex_trade_journal (
            id SERIAL PRIMARY KEY,
            portfolio_id VARCHAR(100),
            symbol VARCHAR(20),
            side VARCHAR(20),
            note TEXT,
            created_at TIMESTAMP
        )
    """))

    db.execute(text("""
        CREATE TABLE IF NOT EXISTS forex_price_history (
            id SERIAL PRIMARY KEY,
            symbol VARCHAR(20),
            asof TIMESTAMP,
            open DOUBLE PRECISION,
            high DOUBLE PRECISION,
            low DOUBLE PRECISION,
            close DOUBLE PRECISION,
            volume DOUBLE PRECISION
        )
    """))

    for sym, side, lots, entry, current, mv, pnl in [
        ("EURUSD", "BUY", 1.00, 1.06782, 1.07182, 107182.00, 400.00),
        ("USDJPY", "BUY", 0.75, 156.240, 158.420, 118815.00, 1032.56),
        ("GBPUSD", "BUY", 0.60, 1.26145, 1.26305, 75783.00, 96.00),
        ("AUDUSD", "SELL", 1.00, 0.66680, 0.66410, 66410.00, 270.00),
    ]:
        db.execute(text("""
            INSERT INTO forex_positions (
                portfolio_id, symbol, side, lots, entry_price, current_price,
                market_value, unrealized_pnl, updated_at
            )
            VALUES (
                :portfolio_id, :symbol, :side, :lots, :entry, :current,
                :mv, :pnl, :now
            )
        """), {
            "portfolio_id": portfolio_id, "symbol": sym, "side": side, "lots": lots,
            "entry": entry, "current": current, "mv": mv, "pnl": pnl, "now": now,
        })

    for sym, side, typ, qty, price, status in [
        ("EURUSD", "BUY", "MARKET", 100000, 1.07182, "filled"),
        ("USDJPY", "BUY", "MARKET", 75000, 158.420, "filled"),
        ("AUDUSD", "SELL", "LIMIT", 100000, 0.66410, "open"),
    ]:
        db.execute(text("""
            INSERT INTO forex_orders (
                portfolio_id, symbol, side, order_type, quantity, price, status, created_at
            )
            VALUES (
                :portfolio_id, :symbol, :side, :typ, :qty, :price, :status, :now
            )
        """), {
            "portfolio_id": portfolio_id, "symbol": sym, "side": side,
            "typ": typ, "qty": qty, "price": price, "status": status, "now": now,
        })

    db.execute(text("""
        INSERT INTO forex_trade_journal (
            portfolio_id, symbol, side, note, created_at
        )
        VALUES (
            :portfolio_id, 'EURUSD', 'BUY', 'Demo Forex validation journal entry.', :now
        )
    """), {"portfolio_id": portfolio_id, "now": now})

    price = 1.071
    for i in range(90):
        ts = now - timedelta(hours=(90 - i))
        openp = price
        price = price + ((i % 8) - 3.5) * 0.00016 + (0.00021 if 18 < i < 55 else -0.00006)
        closep = price
        db.execute(text("""
            INSERT INTO forex_price_history (
                symbol, asof, open, high, low, close, volume
            )
            VALUES (
                'EURUSD', :asof, :open, :high, :low, :close, :volume
            )
        """), {
            "asof": ts,
            "open": openp,
            "high": max(openp, closep) + 0.00035,
            "low": min(openp, closep) - 0.00031,
            "close": closep,
            "volume": 1000 + i * 7,
        })

    db.commit()
    return {"status": "SEEDED", "portfolio_id": portfolio_id, "positions": 4, "orders": 3, "price_rows": 90}
