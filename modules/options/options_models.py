"""
modules/options/options_models.py
DB table for persisting options positions and orders locally.
Auto-created on first load — no migration needed.
"""
from __future__ import annotations
import logging
from sqlalchemy import text
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

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

    from modules.options.options_portfolio_engine import parse_occ_symbol
    parsed = parse_occ_symbol(req.option_symbol)

    now = datetime.now(timezone.utc).isoformat()
    db.execute(text("""
        INSERT INTO options_orders
        (id,tenant_id,user_id,broker_order_id,option_symbol,underlying,option_type,
         strike,expiry,qty,side,order_type,limit_price,status,fill_price,filled_qty,
         error_msg,created_at,updated_at)
        VALUES
        (:id,:tid,:uid,:bid,:sym,:underlying,:otype2,
         :strike,:expiry,:qty,:side,:otype,:lp,:status,:fp,:fq,
         :err,:now,:now)
    """), {
        "id": oid, "tid": tenant_id, "uid": user_id,
        "bid": resp.order_id, "sym": req.option_symbol,
        "underlying": parsed.get("underlying") or "",
        "otype2": parsed.get("option_type") or "",
        "strike": parsed.get("strike") or 0.0,
        "expiry": parsed.get("expiry") or "",
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


def get_order_by_id(db, tenant_id: str, order_id: str) -> dict | None:
    """
    Single options order by id, scoped to tenant_id. Never raises;
    returns None on any failure (not found, doesn't belong to
    tenant_id, or a database error).
    """
    ensure_tables(db)
    try:
        row = db.execute(text("""
            SELECT id, tenant_id, user_id, broker_order_id, option_symbol,
                   underlying, option_type, strike, expiry, qty, side,
                   order_type, limit_price, status, fill_price, filled_qty,
                   error_msg, created_at, updated_at
            FROM options_orders
            WHERE id = :id AND tenant_id = :tid
        """), {"id": order_id, "tid": tenant_id}).fetchone()
        return dict(row._mapping) if row else None
    except Exception:
        return None


_TERMINAL_STATUSES = ("filled", "canceled", "cancelled", "rejected", "expired")


def get_open_orders(db, tenant_id: str) -> list[dict]:
    """
    Locally-stored options orders that aren't in a terminal broker status
    yet -- candidates for reconciliation against the broker's current
    order status. Never raises; returns [] on any failure.
    """
    ensure_tables(db)
    try:
        placeholders = ",".join(f":s{i}" for i in range(len(_TERMINAL_STATUSES)))
        params = {f"s{i}": s for i, s in enumerate(_TERMINAL_STATUSES)}
        params["tid"] = tenant_id

        rows = db.execute(
            text(f"""
                SELECT id, tenant_id, user_id, broker_order_id, option_symbol,
                       underlying, side, qty, status, fill_price, filled_qty
                FROM options_orders
                WHERE tenant_id = :tid
                  AND (status IS NULL OR LOWER(status) NOT IN ({placeholders}))
                  AND broker_order_id IS NOT NULL
                  AND broker_order_id != ''
            """),
            params,
        ).fetchall()
        return [dict(r._mapping) for r in rows]
    except Exception:
        return []


def upsert_positions(db, tenant_id: str, user_id: str, positions: list) -> int:
    """
    Replace the persisted options_positions snapshot for this tenant with
    the current live/simulated position list. A broker position fetch is
    always a full current-state snapshot, not an incremental order, so
    this clears and reinserts rather than trying to diff row by row.

    `positions` accepts OptionsPosition/NormalizedOptionPosition objects
    or plain dicts -- anything with the expected attributes/keys. Never
    raises; returns 0 on failure so a persistence hiccup never blocks the
    live position view this is called from.
    """
    ensure_tables(db)

    def _get(p, key, default=None):
        if isinstance(p, dict):
            return p.get(key, default)
        return getattr(p, key, default)

    try:
        db.execute(
            text("DELETE FROM options_positions WHERE tenant_id = :tid"),
            {"tid": tenant_id},
        )

        now = datetime.now(timezone.utc).isoformat()
        count = 0

        for p in positions or []:
            qty = float(_get(p, "qty", 0.0) or 0.0)
            if qty == 0:
                continue

            db.execute(
                text("""
                    INSERT INTO options_positions
                    (id, tenant_id, user_id, option_symbol, underlying, option_type,
                     strike, expiry, dte, qty, avg_cost, market_value, unrealized_pnl,
                     delta, source, updated_at)
                    VALUES
                    (:id, :tid, :uid, :sym, :underlying, :otype,
                     :strike, :expiry, :dte, :qty, :avg_cost, :mv, :upnl,
                     :delta, :source, :now)
                """),
                {
                    "id": str(uuid.uuid4()),
                    "tid": tenant_id,
                    "uid": user_id,
                    "sym": str(_get(p, "option_symbol", "") or ""),
                    "underlying": str(_get(p, "underlying", "") or ""),
                    "otype": str(_get(p, "option_type", "") or ""),
                    "strike": float(_get(p, "strike", 0.0) or 0.0),
                    "expiry": str(_get(p, "expiry", "") or ""),
                    "dte": int(_get(p, "dte", 0) or 0),
                    "qty": qty,
                    "avg_cost": float(_get(p, "avg_cost", 0.0) or 0.0),
                    "mv": float(_get(p, "market_value", 0.0) or 0.0),
                    "upnl": float(_get(p, "unrealized_pnl", 0.0) or 0.0),
                    "delta": float(_get(p, "delta", 0.0) or 0.0),
                    "source": str(_get(p, "source", "alpaca") or "alpaca"),
                    "now": now,
                },
            )
            count += 1

        db.commit()
        return count

    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return 0


def get_positions(db, tenant_id: str) -> list[dict]:
    """
    Pure read of the persisted options_positions snapshot for a tenant.
    Never raises; returns [] if the table is missing or empty.
    """
    ensure_tables(db)
    try:
        rows = db.execute(
            text("""
                SELECT option_symbol, underlying, option_type, strike, expiry,
                       dte, qty, avg_cost, market_value, unrealized_pnl, delta,
                       source, updated_at
                FROM options_positions
                WHERE tenant_id = :tid
            """),
            {"tid": tenant_id},
        ).fetchall()
        return [dict(r._mapping) for r in rows]
    except Exception:
        return []


def sync_option_orders(db, broker, tenant_id):
    rows = db.execute(text("""
        SELECT broker_order_id
        FROM options_orders
        WHERE tenant_id = :tid
    """), {"tid": tenant_id}).fetchall()

    for row in rows:
        oid = row[0]

        if not oid:
            continue

        order = broker.get_order(oid)

        if not order:
            continue

        update_order_status(
            db=db,
            broker_order_id=oid,
            status=order.get("status", "unknown"),
            fill_price=float(order["filled_avg_price"])
            if order.get("filled_avg_price")
            else None,
            filled_qty=float(order["filled_qty"])
            if order.get("filled_qty")
            else None,
        )


def update_order_status(
    db,
    broker_order_id: str,
    status: str,
    fill_price: float | None = None,
    filled_qty: float | None = None,
):
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()

    result = db.execute(text("""
        UPDATE options_orders
        SET
            status = :status,
            fill_price = COALESCE(:fill_price, fill_price),
            filled_qty = COALESCE(:filled_qty, filled_qty),
            updated_at = :updated_at
        WHERE broker_order_id = :broker_order_id
    """), {
        "status": status,
        "fill_price": fill_price,
        "filled_qty": filled_qty,
        "updated_at": now,
        "broker_order_id": broker_order_id,
    })

    try:
        db.commit()
    except Exception:
        logger.exception(
            "Failed to commit order status update | broker_order_id=%s", broker_order_id,
        )