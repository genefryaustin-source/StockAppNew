"""
modules/forex/forex_order_management_engine.py

Order lifecycle management for the Forex subsystem.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from sqlalchemy import text
except Exception:
    text=None

from modules.forex.forex_trade_execution_engine import get_forex_trade_execution_engine


class ForexOrderManagementEngine:

    def __init__(self, db=None):
        self.db=db
        self.execution=get_forex_trade_execution_engine(db=db)

    def submit(self, **kwargs):
        return self.execution.submit_order(**kwargs)

    def cancel(self, broker_order_id:str)->Dict[str,Any]:
        if self.db is None or text is None:
            return {"status":"unsupported","message":"Database unavailable."}

        self.db.execute(text("""
            UPDATE forex_trade_orders
            SET status='cancelled'
            WHERE broker_order_id=:id
              AND status='open'
        """),{"id":broker_order_id})
        self.db.commit()
        return {
            "status":"cancelled",
            "broker_order_id":broker_order_id,
            "timestamp":datetime.now(timezone.utc).isoformat(),
        }

    def open_orders(self)->List[Dict[str,Any]]:
        if self.db is None or text is None:
            return []

        rows=self.db.execute(text("""
            SELECT *
            FROM forex_trade_orders
            WHERE status='open'
            ORDER BY created_at DESC
        """)).fetchall()

        return [dict(r._mapping) for r in rows]

    def filled_orders(self)->List[Dict[str,Any]]:
        if self.db is None or text is None:
            return []

        rows=self.db.execute(text("""
            SELECT *
            FROM forex_trade_orders
            WHERE status='filled'
            ORDER BY filled_at DESC
        """)).fetchall()

        return [dict(r._mapping) for r in rows]

    def order_status(self, broker_order_id:str)->Optional[Dict[str,Any]]:
        if self.db is None or text is None:
            return None

        row=self.db.execute(text("""
            SELECT *
            FROM forex_trade_orders
            WHERE broker_order_id=:id
            LIMIT 1
        """),{"id":broker_order_id}).fetchone()

        return dict(row._mapping) if row else None


_ENGINE=None

def get_forex_order_management_engine(db=None):
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None):
        _ENGINE=ForexOrderManagementEngine(db=db)
    return _ENGINE
