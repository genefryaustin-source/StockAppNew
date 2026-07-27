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
    ensure_security_master_table(db)

    rows = db.execute(text("""
        SELECT DISTINCT symbol
        FROM universe_symbols
        WHERE symbol IS NOT NULL
        ORDER BY symbol
    """)).fetchall()

    now = datetime.now(UTC).isoformat()

    inserted = 0
    for row in rows:
        sym = row[0].strip().upper()
        if not sym:
            continue

        db.execute(text("""
            INSERT OR IGNORE INTO security_master (
                symbol, exchange, is_etf, sector, industry, source, updated_at
            )
            VALUES (
                :symbol, NULL, 0, NULL, NULL, 'universe_seed', :updated_at
            )
        """), {
            "symbol": sym,
            "updated_at": now,
        })

        inserted += 1

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