
"""
modules/forex/forex_database_cache.py
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Optional

from sqlalchemy import text


class ForexDatabaseCache:

    def __init__(self, db):
        self.db=db

    def ensure_tables(self)->None:
        self.db.execute(text("""
        CREATE TABLE IF NOT EXISTS forex_quote_cache(
            pair VARCHAR(20) PRIMARY KEY,
            mid DOUBLE PRECISION,
            bid DOUBLE PRECISION,
            ask DOUBLE PRECISION,
            provider VARCHAR(100),
            updated_at TIMESTAMP
        )
        """))
        self.db.commit()

    def save_quote(self, quote:dict)->None:
        self.ensure_tables()
        self.db.execute(text("""
        INSERT INTO forex_quote_cache
        (pair,mid,bid,ask,provider,updated_at)
        VALUES
        (:pair,:mid,:bid,:ask,:provider,:updated)
        ON CONFLICT(pair)
        DO UPDATE SET
            mid=EXCLUDED.mid,
            bid=EXCLUDED.bid,
            ask=EXCLUDED.ask,
            provider=EXCLUDED.provider,
            updated_at=EXCLUDED.updated_at
        """),{
            "pair":quote.get("pair"),
            "mid":quote.get("mid"),
            "bid":quote.get("bid"),
            "ask":quote.get("ask"),
            "provider":quote.get("provider"),
            "updated":datetime.now(timezone.utc).replace(tzinfo=None)
        })
        self.db.commit()

    def save_quotes(self, quotes:Iterable[dict])->None:
        for q in quotes:
            self.save_quote(q)

    def get_quote(self,pair:str)->Optional[dict]:
        self.ensure_tables()
        row=self.db.execute(text("""
        SELECT *
        FROM forex_quote_cache
        WHERE pair=:pair
        """),{"pair":pair}).fetchone()
        if not row:
            return None
        return dict(row._mapping)

    def clear(self)->None:
        self.ensure_tables()
        self.db.execute(text("DELETE FROM forex_quote_cache"))
        self.db.commit()
