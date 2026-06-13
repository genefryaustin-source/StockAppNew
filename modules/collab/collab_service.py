"""
modules/collab/collab_service.py

Collaboration service — all DB operations for team features.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import text


def _now():
    return datetime.now(timezone.utc)


def _ensure_tables(db):
    """Create collaboration tables if they don't exist yet."""
    try:
        db.rollback()
    except Exception:
        pass
    try:
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS team_messages (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                user_email TEXT NOT NULL,
                body TEXT NOT NULL,
                ticker_tags TEXT,
                msg_type TEXT DEFAULT 'text',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_deleted INTEGER DEFAULT 0
            )
        """))
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS watchlist_shares (
                id TEXT PRIMARY KEY,
                watchlist_id TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                shared_by TEXT NOT NULL,
                can_edit INTEGER DEFAULT 0,
                shared_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                note TEXT
            )
        """))
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS chart_annotations (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                user_email TEXT NOT NULL,
                symbol TEXT NOT NULL,
                body TEXT NOT NULL,
                annotation_type TEXT DEFAULT 'note',
                price_at TEXT,
                is_pinned INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_deleted INTEGER DEFAULT 0
            )
        """))
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS screener_presets (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                user_email TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                filters_json TEXT NOT NULL,
                query_text TEXT,
                is_shared INTEGER DEFAULT 0,
                result_count INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        db.execute(text("""
                CREATE TABLE IF NOT EXISTS activity_events (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    user_email TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    symbol TEXT,
                    detail TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))

        db.commit()

    except Exception:
        db.rollback()
        raise


import uuid


def _uuid() -> str:
    return str(uuid.uuid4())


# ─────────────────────────────────────────────────────────────
# Team Messages
# ─────────────────────────────────────────────────────────────

def send_message(db, tenant_id: str, user_id: str, user_email: str,
                 body: str, msg_type: str = "text") -> dict:
    """Post a message to the team chat."""
    _ensure_tables(db)

    # Extract $TICKER tags from message
    tags = re.findall(r'\$([A-Z]{1,5})\b', body.upper())
    ticker_tags = ",".join(f"${t}" for t in dict.fromkeys(tags)) if tags else None

    msg_id = _uuid()
    db.execute(text("""
        INSERT INTO team_messages
            (id, tenant_id, user_id, user_email, body, ticker_tags, msg_type, created_at, is_deleted)
        VALUES
            (:id, :tid, :uid, :email, :body, :tags, :mtype, :ts, 0)
    """), {
        "id":    msg_id,
        "tid":   tenant_id,
        "uid":   user_id,
        "email": user_email,
        "body":  body.strip(),
        "tags":  ticker_tags,
        "mtype": msg_type,
        "ts":    _now().isoformat(),
    })
    db.commit()

    # Log activity
    _log_activity(db, tenant_id, user_id, user_email, "message",
                  detail=f"Sent message{f' about {ticker_tags}' if ticker_tags else ''}")

    return {"id": msg_id, "body": body, "ticker_tags": ticker_tags}


def get_messages(db, tenant_id: str, limit: int = 50,
                 ticker: str = None) -> list[dict]:
    """Fetch recent messages for a tenant, optionally filtered by ticker."""
    _ensure_tables(db)

    if ticker:
        rows = db.execute(text("""
            SELECT id, user_email, body, ticker_tags, msg_type, created_at
            FROM team_messages
            WHERE tenant_id = :tid AND is_deleted = 0
              AND (ticker_tags LIKE :tag OR body LIKE :tag2)
            ORDER BY created_at DESC LIMIT :lim
        """), {"tid": tenant_id, "tag": f"%${ticker.upper()}%",
               "tag2": f"%{ticker.upper()}%", "lim": limit}).fetchall()
    else:
        rows = db.execute(text("""
            SELECT id, user_email, body, ticker_tags, msg_type, created_at
            FROM team_messages
            WHERE tenant_id = :tid AND is_deleted = 0
            ORDER BY created_at DESC LIMIT :lim
        """), {"tid": tenant_id, "lim": limit}).fetchall()

    return [
        {
            "id":          str(r[0]),
            "user_email":  str(r[1]),
            "user_name":   str(r[1]).split("@")[0],
            "body":        str(r[2]),
            "ticker_tags": str(r[3]) if r[3] else None,
            "msg_type":    str(r[4]),
            "created_at":  str(r[5])[:16].replace("T", " "),
        }
        for r in reversed(rows)  # oldest first for display
    ]


def get_team_members(db, tenant_id: str) -> list[dict]:
    """Get all active users in a tenant."""
    try:
        rows = db.execute(text("""
            SELECT id, email, role, created_at
            FROM users
            WHERE tenant_id = :tid AND COALESCE(is_active, 1) = 1
            ORDER BY email
        """), {"tid": tenant_id}).fetchall()
        return [{"id": str(r[0]), "email": str(r[1]),
                 "name": str(r[1]).split("@")[0], "role": str(r[2])}
                for r in rows]
    except Exception:
        return []


# ─────────────────────────────────────────────────────────────
# Chart Annotations
# ─────────────────────────────────────────────────────────────

def add_annotation(db, tenant_id: str, user_id: str, user_email: str,
                   symbol: str, body: str,
                   annotation_type: str = "note",
                   price_at: str = None,
                   is_pinned: bool = False) -> str:
    """Add a chart annotation for a symbol."""
    _ensure_tables(db)
    ann_id = _uuid()
    db.execute(text("""
        INSERT INTO chart_annotations
            (id, tenant_id, user_id, user_email, symbol, body,
             annotation_type, price_at, is_pinned, created_at, updated_at, is_deleted)
        VALUES
            (:id, :tid, :uid, :email, :sym, :body,
             :atype, :price, :pinned, :ts, :ts, 0)
    """), {
        "id":     ann_id,
        "tid":    tenant_id,
        "uid":    user_id,
        "email":  user_email,
        "sym":    symbol.upper(),
        "body":   body.strip(),
        "atype":  annotation_type,
        "price":  price_at,
        "pinned": 1 if is_pinned else 0,
        "ts":     _now().isoformat(),
    })
    db.commit()
    _log_activity(db, tenant_id, user_id, user_email, "annotation",
                  symbol=symbol, detail=f"Added {annotation_type} note on {symbol}")
    return ann_id


def get_annotations(db, tenant_id: str, symbol: str) -> list[dict]:
    """Get all team annotations for a symbol."""
    _ensure_tables(db)
    rows = db.execute(text("""
        SELECT id, user_email, body, annotation_type, price_at, is_pinned, created_at
        FROM chart_annotations
        WHERE tenant_id = :tid AND symbol = :sym AND is_deleted = 0
        ORDER BY is_pinned DESC, created_at DESC
    """), {"tid": tenant_id, "sym": symbol.upper()}).fetchall()

    return [
        {
            "id":              str(r[0]),
            "user_email":      str(r[1]),
            "user_name":       str(r[1]).split("@")[0],
            "body":            str(r[2]),
            "annotation_type": str(r[3]),
            "price_at":        str(r[4]) if r[4] else None,
            "is_pinned":       bool(r[5]),
            "created_at":      str(r[6])[:16].replace("T", " "),
        }
        for r in rows
    ]


def delete_annotation(db, ann_id: str, user_id: str, tenant_id: str):
    """Soft-delete an annotation (owner or admin only)."""
    db.execute(text("""
        UPDATE chart_annotations SET is_deleted = 1
        WHERE id = :id AND tenant_id = :tid
          AND (user_id = :uid OR :uid IN (
              SELECT id FROM users WHERE tenant_id = :tid AND role = 'super_admin'
          ))
    """), {"id": ann_id, "tid": tenant_id, "uid": user_id})
    db.commit()


# ─────────────────────────────────────────────────────────────
# Shared Watchlists
# ─────────────────────────────────────────────────────────────

def share_watchlist(db, watchlist_id: str, tenant_id: str,
                    user_id: str, can_edit: bool = False,
                    note: str = None) -> str:
    """Share a watchlist with the whole tenant."""
    _ensure_tables(db)

    # Remove existing share if any
    db.execute(text(
        "DELETE FROM watchlist_shares WHERE watchlist_id = :wid AND tenant_id = :tid"
    ), {"wid": watchlist_id, "tid": tenant_id})

    share_id = _uuid()
    db.execute(text("""
        INSERT INTO watchlist_shares
            (id, watchlist_id, tenant_id, shared_by, can_edit, shared_at, note)
        VALUES
            (:id, :wid, :tid, :uid, :edit, :ts, :note)
    """), {
        "id":   share_id,
        "wid":  watchlist_id,
        "tid":  tenant_id,
        "uid":  user_id,
        "edit": 1 if can_edit else 0,
        "ts":   _now().isoformat(),
        "note": note,
    })
    db.commit()
    return share_id


def unshare_watchlist(db, watchlist_id: str, tenant_id: str):
    db.execute(text(
        "DELETE FROM watchlist_shares WHERE watchlist_id = :wid AND tenant_id = :tid"
    ), {"wid": watchlist_id, "tid": tenant_id})
    db.commit()


def get_shared_watchlists(db, tenant_id: str) -> list[dict]:
    """Get all watchlists shared within a tenant."""
    _ensure_tables(db)
    rows = db.execute(text("""
        SELECT ws.id, ws.watchlist_id, w.name, ws.shared_by, ws.can_edit,
               ws.shared_at, ws.note,
               (SELECT COUNT(*) FROM watchlist_items wi WHERE wi.watchlist_id = w.id) as item_count
        FROM watchlist_shares ws
        JOIN watchlists w ON ws.watchlist_id = w.id
        WHERE ws.tenant_id = :tid
        ORDER BY ws.shared_at DESC
    """), {"tid": tenant_id}).fetchall()

    return [
        {
            "share_id":     str(r[0]),
            "watchlist_id": str(r[1]),
            "name":         str(r[2]),
            "shared_by":    str(r[3]).split("@")[0] if "@" in str(r[3]) else str(r[3]),
            "can_edit":     bool(r[4]),
            "shared_at":    str(r[5])[:10],
            "note":         str(r[6]) if r[6] else None,
            "item_count":   int(r[7] or 0),
        }
        for r in rows
    ]


# ─────────────────────────────────────────────────────────────
# Screener Presets
# ─────────────────────────────────────────────────────────────

def save_screener_preset(db, tenant_id: str, user_id: str, user_email: str,
                         name: str, filters: dict, query_text: str = None,
                         is_shared: bool = False, description: str = None,
                         result_count: int = None) -> str:
    """Save a screener filter configuration."""
    _ensure_tables(db)
    preset_id = _uuid()
    db.execute(text("""
        INSERT INTO screener_presets
            (id, tenant_id, user_id, user_email, name, description,
             filters_json, query_text, is_shared, result_count,
             created_at, updated_at)
        VALUES
            (:id, :tid, :uid, :email, :name, :desc,
             :filters, :query, :shared, :count,
             :ts, :ts)
    """), {
        "id":      preset_id,
        "tid":     tenant_id,
        "uid":     user_id,
        "email":   user_email,
        "name":    name,
        "desc":    description,
        "filters": json.dumps(filters),
        "query":   query_text,
        "shared":  1 if is_shared else 0,
        "count":   result_count,
        "ts":      _now().isoformat(),
    })
    db.commit()
    _log_activity(db, tenant_id, user_id, user_email, "screener_preset",
                  detail=f"Saved screener '{name}'" + (" (shared)" if is_shared else ""))
    return preset_id


def get_screener_presets(db, tenant_id: str, user_id: str) -> list[dict]:
    """Get screener presets: own presets + all shared in tenant."""
    _ensure_tables(db)
    rows = db.execute(text("""
        SELECT id, user_email, name, description, filters_json,
               query_text, is_shared, result_count, created_at
        FROM screener_presets
        WHERE tenant_id = :tid
          AND (user_id = :uid OR is_shared = 1)
        ORDER BY is_shared DESC, created_at DESC
    """), {"tid": tenant_id, "uid": user_id}).fetchall()

    results = []
    for r in rows:
        try:
            filters = json.loads(str(r[4]) or "{}")
        except Exception:
            filters = {}
        results.append({
            "id":           str(r[0]),
            "owner":        str(r[1]).split("@")[0],
            "name":         str(r[2]),
            "description":  str(r[3]) if r[3] else None,
            "filters":      filters,
            "query_text":   str(r[5]) if r[5] else None,
            "is_shared":    bool(r[6]),
            "result_count": int(r[7] or 0),
            "created_at":   str(r[8])[:10],
        })
    return results


def delete_screener_preset(db, preset_id: str, user_id: str, tenant_id: str):
    db.execute(text("""
        DELETE FROM screener_presets
        WHERE id = :id AND tenant_id = :tid AND user_id = :uid
    """), {"id": preset_id, "tid": tenant_id, "uid": user_id})
    db.commit()


# ─────────────────────────────────────────────────────────────
# Activity Feed
# ─────────────────────────────────────────────────────────────

def _log_activity(db, tenant_id: str, user_id: str, user_email: str,
                  event_type: str, symbol: str = None, detail: str = None):
    """Internal helper to log an activity event."""
    try:
        db.execute(text("""
            INSERT INTO activity_events
                (id, tenant_id, user_id, user_email, event_type, symbol, detail, created_at)
            VALUES
                (:id, :tid, :uid, :email, :etype, :sym, :detail, :ts)
        """), {
            "id":     _uuid(),
            "tid":    tenant_id,
            "uid":    user_id,
            "email":  user_email,
            "etype":  event_type,
            "sym":    symbol,
            "detail": detail,
            "ts":     _now().isoformat(),
        })
        db.commit()
    except Exception:
        db.rollback()
        raise


def get_activity_feed(db, tenant_id: str, limit: int = 30,
                      hours: int = 24) -> list[dict]:
    """Recent team activity for the activity feed widget."""
    _ensure_tables(db)
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    rows = db.execute(text("""
        SELECT user_email, event_type, symbol, detail, created_at
        FROM activity_events
        WHERE tenant_id = :tid AND created_at >= :cutoff
        ORDER BY created_at DESC LIMIT :lim
    """), {"tid": tenant_id, "cutoff": cutoff, "lim": limit}).fetchall()

    icons = {
        "message":        "💬",
        "annotation":     "📌",
        "watchlist_add":  "👁",
        "screener_run":   "🔍",
        "screener_preset":"💾",
        "report_gen":     "📄",
    }

    return [
        {
            "user":       str(r[0]).split("@")[0],
            "event_type": str(r[1]),
            "icon":       icons.get(str(r[1]), "•"),
            "symbol":     str(r[2]) if r[2] else None,
            "detail":     str(r[3]) if r[3] else "",
            "time":       str(r[4])[:16].replace("T", " "),
        }
        for r in rows
    ]


def log_activity(db, tenant_id: str, user_id: str, user_email: str,
                 event_type: str, symbol: str = None, detail: str = None):
    """Public wrapper — call from other modules to log activity."""
    _log_activity(db, tenant_id, user_id, user_email, event_type, symbol, detail)