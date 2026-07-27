from __future__ import annotations
from typing import Any, Dict, List, Optional
import sqlite3, uuid
try:
    from modules.forex._forex_runtime_common import DEFAULT_DB_PATH, iso, dumps, loads
except Exception:
    from _forex_runtime_common import DEFAULT_DB_PATH, iso, dumps, loads

class ForexPersistenceEngine:
    """SQLite-backed persistence layer for Forex runtime snapshots, events, and key/value state."""
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._ensure()
    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    def _ensure(self) -> None:
        with self.connect() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS forex_runtime_snapshots (id TEXT PRIMARY KEY, snapshot_type TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL)''')
            conn.execute('''CREATE TABLE IF NOT EXISTS forex_runtime_events (id TEXT PRIMARY KEY, event_type TEXT NOT NULL, severity TEXT NOT NULL, message TEXT NOT NULL, payload TEXT, created_at TEXT NOT NULL)''')
            conn.execute('''CREATE TABLE IF NOT EXISTS forex_runtime_kv (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL)''')
    def save_snapshot(self, snapshot_type: str, payload: Dict[str, Any]) -> str:
        sid = str(uuid.uuid4())
        with self.connect() as conn:
            conn.execute('INSERT INTO forex_runtime_snapshots VALUES (?, ?, ?, ?)', (sid, snapshot_type, dumps(payload), iso()))
        return sid
    def list_snapshots(self, snapshot_type: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        sql, args = 'SELECT * FROM forex_runtime_snapshots', []
        if snapshot_type:
            sql += ' WHERE snapshot_type = ?'; args.append(snapshot_type)
        sql += ' ORDER BY created_at DESC LIMIT ?'; args.append(int(limit))
        with self.connect() as conn: rows = conn.execute(sql, args).fetchall()
        return [{**dict(r), 'payload': loads(r['payload'], {})} for r in rows]
    def log_event(self, event_type: str, message: str, severity: str = 'info', payload: Optional[Dict[str, Any]] = None) -> str:
        eid = str(uuid.uuid4())
        with self.connect() as conn:
            conn.execute('INSERT INTO forex_runtime_events VALUES (?, ?, ?, ?, ?, ?)', (eid, event_type, severity, message, dumps(payload or {}), iso()))
        return eid
    def list_events(self, severity: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        sql, args = 'SELECT * FROM forex_runtime_events', []
        if severity:
            sql += ' WHERE severity = ?'; args.append(severity)
        sql += ' ORDER BY created_at DESC LIMIT ?'; args.append(int(limit))
        with self.connect() as conn: rows = conn.execute(sql, args).fetchall()
        return [{**dict(r), 'payload': loads(r['payload'], {})} for r in rows]
    def set_value(self, key: str, value: Any) -> None:
        with self.connect() as conn:
            conn.execute('''INSERT INTO forex_runtime_kv (key,value,updated_at) VALUES (?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at''', (key, dumps(value), iso()))
    def get_value(self, key: str, default: Any = None) -> Any:
        with self.connect() as conn: row = conn.execute('SELECT value FROM forex_runtime_kv WHERE key=?', (key,)).fetchone()
        return loads(row['value'], default) if row else default
