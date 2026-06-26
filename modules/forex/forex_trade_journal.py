"""
modules/forex/forex_trade_journal.py

Trade journal service for the institutional FX terminal.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from sqlalchemy import text
except Exception:
    text = None


class ForexTradeJournal:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def add_entry(self, **kwargs) -> Dict[str, Any]:
        if self.db is None or text is None:
            return {"status": "ERROR", "message": "Database unavailable."}
        self.ensure_table()
        payload = {
            "portfolio_id": kwargs.get("portfolio_id"),
            "account_id": kwargs.get("account_id"),
            "symbol": kwargs.get("symbol") or kwargs.get("pair"),
            "side": kwargs.get("side"),
            "note": kwargs.get("note") or kwargs.get("rationale") or "",
            "market_regime": kwargs.get("market_regime"),
            "confidence": kwargs.get("confidence"),
            "created_at": datetime.now(timezone.utc).replace(tzinfo=None),
        }
        self.db.execute(text("""
            INSERT INTO forex_trade_journal (
                portfolio_id, account_id, symbol, side, note, market_regime,
                confidence, created_at
            )
            VALUES (
                :portfolio_id, :account_id, :symbol, :side, :note,
                :market_regime, :confidence, :created_at
            )
        """), payload)
        self.db.commit()
        return {"status": "SAVED", "entry": payload}

    def entries(self, limit: int = 100, **kwargs) -> Dict[str, Any]:
        rows: List[Dict[str, Any]] = []
        if self.db is not None and text is not None:
            try:
                self.ensure_table()
                rows_db = self.db.execute(text("""
                    SELECT *
                    FROM forex_trade_journal
                    ORDER BY created_at DESC
                    LIMIT :limit
                """), {"limit": int(limit)}).fetchall()
                rows = [dict(r._mapping) for r in rows_db]
            except Exception:
                rows = []
        return {"status": "READY", "count": len(rows), "entries": rows}

    def ensure_table(self) -> None:
        if self.db is None or text is None:
            return
        self.db.execute(text("""
            CREATE TABLE IF NOT EXISTS forex_trade_journal (
                id SERIAL PRIMARY KEY,
                portfolio_id VARCHAR(100),
                account_id VARCHAR(100),
                symbol VARCHAR(20),
                side VARCHAR(20),
                note TEXT,
                market_regime VARCHAR(80),
                confidence DOUBLE PRECISION,
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """))
        self.db.commit()


_JOURNAL = None


def get_forex_trade_journal(db: Optional[Any] = None) -> ForexTradeJournal:
    global _JOURNAL
    if _JOURNAL is None or (db is not None and _JOURNAL.db is None):
        _JOURNAL = ForexTradeJournal(db=db)
    return _JOURNAL
