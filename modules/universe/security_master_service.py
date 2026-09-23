from datetime import datetime, UTC
from sqlalchemy import text


def ensure_security_master_table(db):
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS security_master (
            symbol TEXT PRIMARY KEY,
            exchange TEXT,
            is_etf INTEGER NOT NULL DEFAULT 0,
            sector TEXT,
            industry TEXT,
            source TEXT,
            updated_at TEXT
        )
    """))
    db.commit()


def seed_security_master_from_universe_symbols(db):
    """
    Seeds security_master with every symbol currently in universe_symbols
    that isn't there yet (a bare placeholder row -- exchange/sector/etc.
    get filled in later by upsert_security_master_classification via
    "Run Auto Classification").

    Uses "INSERT ... ON CONFLICT (symbol) DO NOTHING" rather than SQLite's
    "INSERT OR IGNORE" shorthand -- the latter is SQLite-only syntax and
    raises a hard SyntaxError against Postgres/Neon in production ("syntax
    error at or near OR"), which aborted this entire function on the very
    first row with no rows seeded at all. ON CONFLICT DO NOTHING is
    supported natively by both SQLite (3.24+) and Postgres, so this one
    statement form works unchanged on both.

    Also batches the insert (500 symbols per statement) instead of
    executing one INSERT per symbol in a loop -- for an 11,000+ symbol
    universe that's ~22 statements instead of 11,000+, avoiding the same
    class of slow one-row-at-a-time pattern that caused the price refresh
    to hang earlier.
    """
    ensure_security_master_table(db)

    rows = db.execute(text("""
        SELECT DISTINCT symbol
        FROM universe_symbols
        WHERE symbol IS NOT NULL
        ORDER BY symbol
    """)).fetchall()

    now = datetime.now(UTC).isoformat()
    symbols = sorted({row[0].strip().upper() for row in rows if row[0] and row[0].strip()})

    inserted = 0
    batch_size = 500
    for batch_start in range(0, len(symbols), batch_size):
        batch = symbols[batch_start:batch_start + batch_size]
        values_sql = ", ".join(f"(:symbol_{i}, NULL, 0, NULL, NULL, 'universe_seed', :updated_at)"
                                for i in range(len(batch)))
        params = {f"symbol_{i}": sym for i, sym in enumerate(batch)}
        params["updated_at"] = now

        db.execute(text(f"""
            INSERT INTO security_master (
                symbol, exchange, is_etf, sector, industry, source, updated_at
            )
            VALUES {values_sql}
            ON CONFLICT (symbol) DO NOTHING
        """), params)
        inserted += len(batch)
        db.commit()

    return inserted


def upsert_security_master_classification(db, symbol: str, exchange: str | None, is_etf: bool):
    now = datetime.now(UTC).isoformat()

    db.execute(text("""
        INSERT INTO security_master (
            symbol, exchange, is_etf, sector, industry, source, updated_at
        )
        VALUES (
            :symbol, :exchange, :is_etf, NULL, NULL, 'classifier', :updated_at
        )
        ON CONFLICT(symbol) DO UPDATE SET
            exchange = excluded.exchange,
            is_etf = excluded.is_etf,
            updated_at = excluded.updated_at,
            source = excluded.source
    """), {
        "symbol": symbol.upper(),
        "exchange": exchange,
        "is_etf": 1 if is_etf else 0,
        "updated_at": now,
    })