"""
modules/crypto/crypto_ai_investigation_repository.py

Sprint CR-5: Autonomous Investigation Engine.

Persists AI-generated investigation reports -- gathered evidence,
narrative summary, and advisory (never auto-actioned) recommendations
-- so a report can be reviewed later, not just shown once and lost.

Follows the same dialect-aware ensure_tables() pattern established
across CR-1 through CR-4.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import text

logger = logging.getLogger(__name__)


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _dialect_name(db: Any) -> str:
    try:
        bind = getattr(db, "bind", None)
        if bind is None and hasattr(db, "get_bind"):
            bind = db.get_bind()
        if bind is not None:
            return bind.dialect.name
    except Exception:
        pass
    try:
        return db.get_bind().dialect.name
    except Exception:
        return "postgresql"


class CryptoAiInvestigationRepository:
    def __init__(self, db=None):
        self.db = db
        self._tables_ready = False

    def ensure_tables(self) -> None:
        if self.db is None:
            return
        if self._tables_ready:
            return

        dialect = _dialect_name(self.db)
        id_column = (
            "id INTEGER PRIMARY KEY AUTOINCREMENT"
            if dialect == "sqlite"
            else "id SERIAL PRIMARY KEY"
        )

        self.db.execute(text(f"""
            CREATE TABLE IF NOT EXISTS crypto_ai_investigations (
                {id_column},
                tenant_id VARCHAR(100),
                address VARCHAR(128) NOT NULL,
                chain VARCHAR(50) NOT NULL,
                status VARCHAR(20) DEFAULT 'COMPLETE',
                risk_level VARCHAR(20),
                summary TEXT,
                recommended_actions TEXT,
                evidence_snapshot TEXT,
                requested_by VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

        try:
            self.db.commit()
        except Exception:
            pass

        self._tables_ready = True

    def save_investigation(
        self, *, tenant_id: Optional[str], address: str, chain: str, status: str,
        risk_level: Optional[str], summary: Optional[str], recommended_actions: Optional[List[str]],
        evidence_snapshot: Dict[str, Any], requested_by: Optional[str] = None,
    ) -> int:
        self.ensure_tables()
        if self.db is None:
            return -1

        self.db.execute(text("""
            INSERT INTO crypto_ai_investigations (
                tenant_id, address, chain, status, risk_level, summary,
                recommended_actions, evidence_snapshot, requested_by
            ) VALUES (
                :tenant_id, :address, :chain, :status, :risk_level, :summary,
                :recommended_actions, :evidence_snapshot, :requested_by
            )
        """), {
            "tenant_id": tenant_id, "address": address.lower(), "chain": chain, "status": status,
            "risk_level": risk_level, "summary": summary,
            "recommended_actions": json.dumps(recommended_actions or []),
            "evidence_snapshot": json.dumps(evidence_snapshot, default=str),
            "requested_by": requested_by,
        })
        try:
            self.db.commit()
        except Exception:
            pass

        dialect = _dialect_name(self.db)
        if dialect == "sqlite":
            row = self.db.execute(text("SELECT last_insert_rowid() AS id")).mappings().first()
        else:
            row = self.db.execute(text(
                "SELECT id FROM crypto_ai_investigations WHERE address = :address ORDER BY created_at DESC LIMIT 1"
            ), {"address": address.lower()}).mappings().first()
        return int(row["id"]) if row and row["id"] is not None else -1

    def list_investigations(self, *, tenant_id: Optional[str] = None, address: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        self.ensure_tables()
        if self.db is None:
            return []
        clauses, params = [], {"limit": limit}
        if tenant_id is not None:
            clauses.append("tenant_id = :tenant_id")
            params["tenant_id"] = tenant_id
        if address is not None:
            clauses.append("address = :address")
            params["address"] = address.lower()
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.db.execute(text(f"""
            SELECT * FROM crypto_ai_investigations {where_sql}
            ORDER BY created_at DESC, id DESC LIMIT :limit
        """), params).mappings().all()

        results = []
        for row in rows:
            item = dict(row)
            for field in ("recommended_actions", "evidence_snapshot"):
                if item.get(field):
                    try:
                        item[field] = json.loads(item[field])
                    except Exception:
                        pass
            results.append(item)
        return results

    def get_investigation(self, investigation_id: int) -> Optional[Dict[str, Any]]:
        matches = self.list_investigations(limit=100000)
        for item in matches:
            if item["id"] == investigation_id:
                return item
        return None


_REPOSITORY: Optional[CryptoAiInvestigationRepository] = None


def get_crypto_ai_investigation_repository(db=None) -> CryptoAiInvestigationRepository:
    return CryptoAiInvestigationRepository(db=db)