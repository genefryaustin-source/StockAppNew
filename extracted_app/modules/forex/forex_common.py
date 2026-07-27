"""
Shared Forex operations utilities.

This module is intentionally dependency-light and safe to import in Streamlit,
CLI jobs, tests, and production runtimes. It provides small helpers used by the
Forex operations center, scheduler, runtime controller, governor, queue, and
dashboards.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta, timezone
from enum import Enum
import hashlib
import json
import math
import os
import random
import sqlite3
import threading
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple


UTC = timezone.utc


def utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def iso_now() -> str:
    return utc_now().isoformat()


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        value = float(value)
        if math.isnan(value) or math.isinf(value):
            return default
        return value
    except Exception:
        return default


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def stable_id(*parts: Any, prefix: str = "fx") -> str:
    raw = "|".join(str(p) for p in parts if p is not None)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def normalize_symbol(symbol: str) -> str:
    return str(symbol or "").replace("/", "").replace("-", "").upper().strip()


def normalize_pair(pair: str) -> str:
    s = normalize_symbol(pair)
    if len(s) == 6:
        return f"{s[:3]}/{s[3:]}"
    return s


def default_pairs() -> List[str]:
    return [
        "EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF", "AUD/USD",
        "USD/CAD", "NZD/USD", "EUR/GBP", "EUR/JPY", "GBP/JPY",
        "AUD/JPY", "CAD/JPY", "EUR/CHF", "AUD/NZD", "GBP/CAD",
    ]
def split_pair(pair: str) -> tuple[str, str]:
    """
    Split a forex pair into base and quote currencies.

    Examples:
        EUR/USD -> ("EUR", "USD")
        EURUSD  -> ("EUR", "USD")
    """
    pair = normalize_pair(pair)

    if "/" in pair:
        base, quote = pair.split("/", 1)
        return base, quote

    if len(pair) == 6:
        return pair[:3], pair[3:]

    return "", ""

def ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


def default_state_dir() -> str:
    return ensure_dir(os.getenv("FOREX_STATE_DIR", os.path.join(os.getcwd(), ".forex_runtime")))


class ForexStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
    RECOVERED = "recovered"


class ForexPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


PRIORITY_WEIGHT = {
    ForexPriority.LOW.value: 10,
    ForexPriority.NORMAL.value: 50,
    ForexPriority.HIGH.value: 80,
    ForexPriority.CRITICAL.value: 100,
}


@dataclass
class ForexJob:
    job_id: str
    job_type: str
    pair: str = ""
    priority: str = ForexPriority.NORMAL.value
    status: str = ForexStatus.PENDING.value
    tenant_id: str = "default"
    payload: Dict[str, Any] = field(default_factory=dict)
    attempts: int = 0
    max_attempts: int = 3
    scheduled_for: str = field(default_factory=iso_now)
    created_at: str = field(default_factory=iso_now)
    updated_at: str = field(default_factory=iso_now)
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    worker_id: Optional[str] = None
    error: Optional[str] = None

    @classmethod
    def create(
        cls,
        job_type: str,
        pair: str = "",
        priority: str = ForexPriority.NORMAL.value,
        tenant_id: str = "default",
        payload: Optional[Dict[str, Any]] = None,
        scheduled_for: Optional[str] = None,
    ) -> "ForexJob":
        payload = payload or {}
        job_id = stable_id(job_type, pair, tenant_id, json.dumps(payload, sort_keys=True), scheduled_for or iso_now(), prefix="fxjob")
        return cls(
            job_id=job_id,
            job_type=job_type,
            pair=normalize_pair(pair),
            priority=priority,
            tenant_id=tenant_id,
            payload=payload,
            scheduled_for=scheduled_for or iso_now(),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ForexStateStore:
    """Simple SQLite state store for local/dev operations and Streamlit Cloud."""

    _lock = threading.RLock()

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path or os.getenv("FOREX_RUNTIME_DB") or os.path.join(default_state_dir(), "forex_runtime.sqlite3")
        ensure_dir(os.path.dirname(self.db_path))
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        return conn

    def initialize(self) -> None:
        with self._lock, self.connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS forex_jobs (
                    job_id TEXT PRIMARY KEY,
                    job_type TEXT NOT NULL,
                    pair TEXT,
                    priority TEXT,
                    status TEXT,
                    tenant_id TEXT,
                    payload TEXT,
                    attempts INTEGER,
                    max_attempts INTEGER,
                    scheduled_for TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    started_at TEXT,
                    finished_at TEXT,
                    worker_id TEXT,
                    error TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS forex_runtime_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT,
                    severity TEXT,
                    message TEXT,
                    payload TEXT,
                    created_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS forex_metrics (
                    metric_key TEXT PRIMARY KEY,
                    metric_value REAL,
                    payload TEXT,
                    updated_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS forex_locks (
                    lock_key TEXT PRIMARY KEY,
                    owner TEXT,
                    expires_at TEXT,
                    updated_at TEXT
                )
            """)

    def upsert_job(self, job: ForexJob | Dict[str, Any]) -> Dict[str, Any]:
        data = job.to_dict() if hasattr(job, "to_dict") else dict(job)
        data["updated_at"] = iso_now()
        payload = json.dumps(data.get("payload") or {}, default=str)
        with self._lock, self.connect() as conn:
            conn.execute("""
                INSERT INTO forex_jobs (
                    job_id, job_type, pair, priority, status, tenant_id, payload, attempts,
                    max_attempts, scheduled_for, created_at, updated_at, started_at,
                    finished_at, worker_id, error
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    job_type=excluded.job_type,
                    pair=excluded.pair,
                    priority=excluded.priority,
                    status=excluded.status,
                    tenant_id=excluded.tenant_id,
                    payload=excluded.payload,
                    attempts=excluded.attempts,
                    max_attempts=excluded.max_attempts,
                    scheduled_for=excluded.scheduled_for,
                    updated_at=excluded.updated_at,
                    started_at=excluded.started_at,
                    finished_at=excluded.finished_at,
                    worker_id=excluded.worker_id,
                    error=excluded.error
            """, (
                data.get("job_id"), data.get("job_type"), data.get("pair"), data.get("priority"),
                data.get("status"), data.get("tenant_id"), payload, int(data.get("attempts") or 0),
                int(data.get("max_attempts") or 3), data.get("scheduled_for"), data.get("created_at") or iso_now(),
                data.get("updated_at") or iso_now(), data.get("started_at"), data.get("finished_at"),
                data.get("worker_id"), data.get("error"),
            ))
        return data

    def list_jobs(self, status: Optional[str] = None, limit: int = 500) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM forex_jobs"
        params: List[Any] = []
        if status:
            sql += " WHERE status = ?"
            params.append(status)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(int(limit))
        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_job(r) for r in rows]

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM forex_jobs WHERE job_id = ?", (job_id,)).fetchone()
        return self._row_to_job(row) if row else None

    def claim_next_job(self, worker_id: str, limit_to_types: Optional[Iterable[str]] = None) -> Optional[Dict[str, Any]]:
        now = iso_now()
        type_filter = ""
        params: List[Any] = [ForexStatus.QUEUED.value, ForexStatus.PENDING.value, now]
        if limit_to_types:
            placeholders = ",".join("?" for _ in limit_to_types)
            type_filter = f" AND job_type IN ({placeholders})"
            params.extend(list(limit_to_types))
        query = f"""
            SELECT * FROM forex_jobs
            WHERE status IN (?, ?) AND scheduled_for <= ? {type_filter}
            ORDER BY
                CASE priority
                    WHEN 'critical' THEN 4
                    WHEN 'high' THEN 3
                    WHEN 'normal' THEN 2
                    ELSE 1
                END DESC,
                scheduled_for ASC,
                created_at ASC
            LIMIT 1
        """
        with self._lock, self.connect() as conn:
            row = conn.execute(query, params).fetchone()
            if not row:
                return None
            job = self._row_to_job(row)
            job["status"] = ForexStatus.RUNNING.value
            job["worker_id"] = worker_id
            job["started_at"] = iso_now()
            job["attempts"] = int(job.get("attempts") or 0) + 1
            self.upsert_job(job)
            return job

    def update_job_status(self, job_id: str, status: str, error: Optional[str] = None, **updates: Any) -> Optional[Dict[str, Any]]:
        job = self.get_job(job_id)
        if not job:
            return None
        job.update(updates)
        job["status"] = status
        job["error"] = error
        job["updated_at"] = iso_now()
        if status in {ForexStatus.SUCCEEDED.value, ForexStatus.FAILED.value, ForexStatus.SKIPPED.value, ForexStatus.CANCELLED.value, ForexStatus.RECOVERED.value}:
            job["finished_at"] = iso_now()
        self.upsert_job(job)
        return job

    def record_event(self, event_type: str, message: str, severity: str = "info", payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        event = {
            "event_type": event_type,
            "severity": severity,
            "message": message,
            "payload": payload or {},
            "created_at": iso_now(),
        }
        with self._lock, self.connect() as conn:
            conn.execute("""
                INSERT INTO forex_runtime_events (event_type, severity, message, payload, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (event_type, severity, message, json.dumps(payload or {}, default=str), event["created_at"]))
        return event

    def recent_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM forex_runtime_events ORDER BY id DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        return [
            {
                "id": r["id"],
                "event_type": r["event_type"],
                "severity": r["severity"],
                "message": r["message"],
                "payload": json.loads(r["payload"] or "{}"),
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    def set_metric(self, key: str, value: float, payload: Optional[Dict[str, Any]] = None) -> None:
        with self._lock, self.connect() as conn:
            conn.execute("""
                INSERT INTO forex_metrics (metric_key, metric_value, payload, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(metric_key) DO UPDATE SET
                    metric_value=excluded.metric_value,
                    payload=excluded.payload,
                    updated_at=excluded.updated_at
            """, (key, safe_float(value), json.dumps(payload or {}, default=str), iso_now()))

    def metrics(self) -> Dict[str, Dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM forex_metrics").fetchall()
        return {
            r["metric_key"]: {
                "value": r["metric_value"],
                "payload": json.loads(r["payload"] or "{}"),
                "updated_at": r["updated_at"],
            }
            for r in rows
        }

    def acquire_lock(self, lock_key: str, owner: str, ttl_seconds: int = 120) -> bool:
        now_dt = utc_now()
        expires = (now_dt + timedelta(seconds=ttl_seconds)).isoformat()
        with self._lock, self.connect() as conn:
            row = conn.execute("SELECT * FROM forex_locks WHERE lock_key = ?", (lock_key,)).fetchone()
            if row and row["expires_at"] and row["expires_at"] > now_dt.isoformat() and row["owner"] != owner:
                return False
            conn.execute("""
                INSERT INTO forex_locks (lock_key, owner, expires_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(lock_key) DO UPDATE SET
                    owner=excluded.owner,
                    expires_at=excluded.expires_at,
                    updated_at=excluded.updated_at
            """, (lock_key, owner, expires, now_dt.isoformat()))
        return True

    def release_lock(self, lock_key: str, owner: str) -> bool:
        with self._lock, self.connect() as conn:
            conn.execute("DELETE FROM forex_locks WHERE lock_key = ? AND owner = ?", (lock_key, owner))
        return True

    def _row_to_job(self, row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "job_id": row["job_id"],
            "job_type": row["job_type"],
            "pair": row["pair"],
            "priority": row["priority"],
            "status": row["status"],
            "tenant_id": row["tenant_id"],
            "payload": json.loads(row["payload"] or "{}"),
            "attempts": row["attempts"],
            "max_attempts": row["max_attempts"],
            "scheduled_for": row["scheduled_for"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "worker_id": row["worker_id"],
            "error": row["error"],
        }


def sample_market_snapshot(pair: str) -> Dict[str, Any]:
    """Deterministic-ish fallback snapshot for dev/test if no live provider is available."""
    pair = normalize_pair(pair)
    seed = int(hashlib.sha1(pair.encode("utf-8")).hexdigest()[:8], 16)
    rng = random.Random(seed + int(time.time() // 3600))
    base = 1.0 + (seed % 2000) / 10000
    if pair.endswith("/JPY"):
        base = 100 + (seed % 6000) / 100
    spread = max(base * rng.uniform(0.00002, 0.00012), 0.00001)
    mid = base * (1 + rng.uniform(-0.01, 0.01))
    return {
        "pair": pair,
        "bid": round(mid - spread / 2, 5 if not pair.endswith("/JPY") else 3),
        "ask": round(mid + spread / 2, 5 if not pair.endswith("/JPY") else 3),
        "mid": round(mid, 5 if not pair.endswith("/JPY") else 3),
        "spread": round(spread, 6),
        "volatility": round(rng.uniform(0.35, 1.85), 3),
        "liquidity_score": round(rng.uniform(55, 98), 2),
        "trend_score": round(rng.uniform(-100, 100), 2),
        "timestamp": iso_now(),
        "source": "deterministic_fallback",
    }


def summarize_jobs(jobs: List[Dict[str, Any]]) -> Dict[str, Any]:
    totals: Dict[str, int] = {}
    by_type: Dict[str, int] = {}
    for j in jobs:
        totals[j.get("status") or "unknown"] = totals.get(j.get("status") or "unknown", 0) + 1
        by_type[j.get("job_type") or "unknown"] = by_type.get(j.get("job_type") or "unknown", 0) + 1
    return {
        "total_jobs": len(jobs),
        "by_status": totals,
        "by_type": by_type,
        "open_jobs": sum(v for k, v in totals.items() if k in {"pending", "queued", "running"}),
        "failed_jobs": totals.get("failed", 0),
        "succeeded_jobs": totals.get("succeeded", 0),
    }


def streamlit_dataframe(df: Any, use_container_width: bool = True) -> None:
    import streamlit as st
    st.dataframe(df, use_container_width=use_container_width, hide_index=True)
