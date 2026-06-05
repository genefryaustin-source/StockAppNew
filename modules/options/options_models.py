"""
modules/options/options_models.py
DB table for persisting options positions and orders locally.
Auto-created on first load — no migration needed.
"""
from __future__ import annotations
from sqlalchemy import text
import uuid

def ensure_tables(db):
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS options_positions (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            user_id TEXT,
            option_symbol TEXT NOT NULL,
            underlying TEXT NOT NULL,
            option_type TEXT,
            strike REAL,
            expiry TEXT,
            dte INTEGER,
            qty REAL,
            avg_cost REAL,
            market_value REAL,
            unrealized_pnl REAL,
            delta REAL,
            source TEXT DEFAULT 'alpaca',
            updated_at TEXT
        )
    """))
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS options_orders (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            user_id TEXT,
            broker_order_id TEXT,
            option_symbol TEXT NOT NULL,
            underlying TEXT,
            option_type TEXT,
            strike REAL,
            expiry TEXT,
            qty INTEGER,
            side TEXT,
            order_type TEXT,
            limit_price REAL,
            status TEXT,
            fill_price REAL,
            filled_qty REAL,
            error_msg TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """))
    try: db.commit()
    except: pass

def save_order(db, tenant_id: str, user_id: str, req, resp) -> str:
    ensure_tables(db)
    oid = str(uuid.uuid4())
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    db.execute(text("""
        INSERT INTO options_orders
        (id,tenant_id,user_id,broker_order_id,option_symbol,qty,side,
         order_type,limit_price,status,fill_price,filled_qty,error_msg,created_at,updated_at)
        VALUES
        (:id,:tid,:uid,:bid,:sym,:qty,:side,:otype,:lp,:status,:fp,:fq,:err,:now,:now)
    """), {
        "id": oid, "tid": tenant_id, "uid": user_id,
        "bid": resp.order_id, "sym": req.option_symbol,
        "qty": req.qty, "side": req.side, "otype": req.order_type,
        "lp": req.limit_price, "status": resp.status,
        "fp": resp.fill_price, "fq": resp.filled_qty,
        "err": resp.error, "now": now,
    })
    try: db.commit()
    except: pass
    return oid

def get_order_history(db, tenant_id: str, limit: int = 50) -> list[dict]:
    ensure_tables(db)
    try:
        rows = db.execute(text("""
            SELECT option_symbol, side, qty, order_type, limit_price,
                   status, fill_price, filled_qty, error_msg, created_at
            FROM options_orders
            WHERE tenant_id = :tid
            ORDER BY created_at DESC LIMIT :lim
        """), {"tid": tenant_id, "lim": limit}).fetchall()
        return [dict(r._mapping) for r in rows]
    except: return []

