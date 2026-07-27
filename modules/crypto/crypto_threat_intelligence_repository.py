"""
modules/crypto/crypto_threat_intelligence_repository.py

Sprint CR-2: Crypto Threat Intelligence.

Three entity types, one shared linking table:

- crypto_threat_actors: a persistent identity (a named/aliased
  scammer, ransomware group, phishing operator, etc.) that can own
  multiple wallet addresses over time.
- crypto_scam_campaigns: a bounded operation (a specific phishing
  site, a specific rug-pull token, a specific fake-exchange scheme)
  with a start/end window, optionally attributed to an actor.
- crypto_fraud_clusters: a group of addresses linked by a specific,
  named clustering method (see crypto_fraud_clustering_engine.py) --
  common funding source or transaction-graph co-occurrence.

crypto_threat_entity_addresses links any of the three entity types to
one or more addresses via an entity_type discriminator column, rather
than three separate, near-identical linking tables -- the query
pattern (list addresses for an entity, list entities for an address)
is the same across all three, so one table with a discriminator keeps
that logic in one place instead of three copies of it.

Follows the same dialect-aware ensure_tables() pattern established in
crypto_wallet_intelligence_repository.py (and, before that,
execution_order_repository.py).
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


VALID_ENTITY_TYPES = {"ACTOR", "CAMPAIGN", "CLUSTER"}


class CryptoThreatIntelligenceRepository:
    def __init__(self, db=None):
        self.db = db
        self._tables_ready = False

    # ------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------

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
            CREATE TABLE IF NOT EXISTS crypto_threat_actors (
                {id_column},
                tenant_id VARCHAR(100),
                name VARCHAR(200) NOT NULL,
                aliases TEXT,
                actor_type VARCHAR(50),
                description TEXT,
                confidence VARCHAR(20) DEFAULT 'MEDIUM',
                first_seen_at TIMESTAMP,
                last_activity_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

        self.db.execute(text(f"""
            CREATE TABLE IF NOT EXISTS crypto_scam_campaigns (
                {id_column},
                tenant_id VARCHAR(100),
                name VARCHAR(200) NOT NULL,
                campaign_type VARCHAR(50),
                status VARCHAR(20) DEFAULT 'ACTIVE',
                actor_id INTEGER,
                description TEXT,
                estimated_victim_count INTEGER,
                estimated_loss_usd DOUBLE PRECISION,
                started_at TIMESTAMP,
                ended_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

        self.db.execute(text(f"""
            CREATE TABLE IF NOT EXISTS crypto_fraud_clusters (
                {id_column},
                tenant_id VARCHAR(100),
                cluster_method VARCHAR(50) NOT NULL,
                cluster_key VARCHAR(200),
                confidence VARCHAR(20) DEFAULT 'MEDIUM',
                member_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

        self.db.execute(text(f"""
            CREATE TABLE IF NOT EXISTS crypto_threat_entity_addresses (
                {id_column},
                entity_type VARCHAR(20) NOT NULL,
                entity_id INTEGER NOT NULL,
                address VARCHAR(128) NOT NULL,
                chain VARCHAR(50),
                role VARCHAR(50),
                evidence TEXT,
                linked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

        try:
            self.db.commit()
        except Exception:
            pass

        self._tables_ready = True

    # ------------------------------------------------------------
    # Threat actors
    # ------------------------------------------------------------

    def create_actor(
        self, *, tenant_id: Optional[str], name: str, actor_type: str,
        aliases: Optional[List[str]] = None, description: Optional[str] = None,
        confidence: str = "MEDIUM",
    ) -> int:
        self.ensure_tables()
        now = _utc_now_naive()
        result = self.db.execute(text("""
            INSERT INTO crypto_threat_actors (
                tenant_id, name, aliases, actor_type, description, confidence,
                first_seen_at, last_activity_at
            ) VALUES (
                :tenant_id, :name, :aliases, :actor_type, :description, :confidence, :now, :now
            )
        """), {
            "tenant_id": tenant_id, "name": name, "aliases": json.dumps(aliases or []),
            "actor_type": actor_type, "description": description, "confidence": confidence, "now": now,
        })
        try:
            self.db.commit()
        except Exception:
            pass
        return self._last_insert_id("crypto_threat_actors")

    def list_actors(self, *, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
        self.ensure_tables()
        if self.db is None:
            return []
        clauses, params = [], {}
        if tenant_id is not None:
            clauses.append("tenant_id = :tenant_id")
            params["tenant_id"] = tenant_id
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.db.execute(text(f"""
            SELECT * FROM crypto_threat_actors {where_sql} ORDER BY last_activity_at DESC
        """), params).mappings().all()
        results = []
        for row in rows:
            item = dict(row)
            if item.get("aliases"):
                try:
                    item["aliases"] = json.loads(item["aliases"])
                except Exception:
                    item["aliases"] = []
            results.append(item)
        return results

    def touch_actor_activity(self, actor_id: int) -> None:
        self.ensure_tables()
        if self.db is None:
            return
        self.db.execute(text("""
            UPDATE crypto_threat_actors SET last_activity_at = :now WHERE id = :actor_id
        """), {"now": _utc_now_naive(), "actor_id": actor_id})
        try:
            self.db.commit()
        except Exception:
            pass

    # ------------------------------------------------------------
    # Scam campaigns
    # ------------------------------------------------------------

    def create_campaign(
        self, *, tenant_id: Optional[str], name: str, campaign_type: str,
        actor_id: Optional[int] = None, description: Optional[str] = None,
        status: str = "ACTIVE",
    ) -> int:
        self.ensure_tables()
        now = _utc_now_naive()
        self.db.execute(text("""
            INSERT INTO crypto_scam_campaigns (
                tenant_id, name, campaign_type, status, actor_id, description, started_at
            ) VALUES (
                :tenant_id, :name, :campaign_type, :status, :actor_id, :description, :now
            )
        """), {
            "tenant_id": tenant_id, "name": name, "campaign_type": campaign_type,
            "status": status, "actor_id": actor_id, "description": description, "now": now,
        })
        try:
            self.db.commit()
        except Exception:
            pass
        return self._last_insert_id("crypto_scam_campaigns")

    def list_campaigns(self, *, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
        self.ensure_tables()
        if self.db is None:
            return []
        clauses, params = [], {}
        if tenant_id is not None:
            clauses.append("tenant_id = :tenant_id")
            params["tenant_id"] = tenant_id
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.db.execute(text(f"""
            SELECT * FROM crypto_scam_campaigns {where_sql} ORDER BY started_at DESC
        """), params).mappings().all()
        return [dict(row) for row in rows]

    def set_campaign_status(self, campaign_id: int, status: str) -> None:
        self.ensure_tables()
        if self.db is None:
            return
        now = _utc_now_naive()
        ended_at_sql = ", ended_at = :now" if status in ("TAKEN_DOWN", "DORMANT") else ""
        self.db.execute(text(f"""
            UPDATE crypto_scam_campaigns SET status = :status {ended_at_sql} WHERE id = :campaign_id
        """), {"status": status, "now": now, "campaign_id": campaign_id})
        try:
            self.db.commit()
        except Exception:
            pass

    # ------------------------------------------------------------
    # Fraud clusters
    # ------------------------------------------------------------

    def create_cluster(
        self, *, tenant_id: Optional[str], cluster_method: str, cluster_key: str, confidence: str = "MEDIUM",
    ) -> int:
        self.ensure_tables()
        self.db.execute(text("""
            INSERT INTO crypto_fraud_clusters (tenant_id, cluster_method, cluster_key, confidence)
            VALUES (:tenant_id, :cluster_method, :cluster_key, :confidence)
        """), {
            "tenant_id": tenant_id, "cluster_method": cluster_method,
            "cluster_key": cluster_key, "confidence": confidence,
        })
        try:
            self.db.commit()
        except Exception:
            pass
        return self._last_insert_id("crypto_fraud_clusters")

    def find_cluster_by_key(self, *, tenant_id: Optional[str], cluster_method: str, cluster_key: str) -> Optional[Dict[str, Any]]:
        self.ensure_tables()
        if self.db is None:
            return None
        row = self.db.execute(text("""
            SELECT * FROM crypto_fraud_clusters
            WHERE cluster_method = :cluster_method AND cluster_key = :cluster_key
              AND (tenant_id = :tenant_id OR (:tenant_id IS NULL AND tenant_id IS NULL))
        """), {"cluster_method": cluster_method, "cluster_key": cluster_key, "tenant_id": tenant_id}).mappings().first()
        return dict(row) if row else None

    def list_clusters(self, *, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
        self.ensure_tables()
        if self.db is None:
            return []
        clauses, params = [], {}
        if tenant_id is not None:
            clauses.append("tenant_id = :tenant_id")
            params["tenant_id"] = tenant_id
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.db.execute(text(f"""
            SELECT * FROM crypto_fraud_clusters {where_sql} ORDER BY member_count DESC, created_at DESC
        """), params).mappings().all()
        return [dict(row) for row in rows]

    def update_cluster_member_count(self, cluster_id: int) -> None:
        self.ensure_tables()
        if self.db is None:
            return
        count_row = self.db.execute(text("""
            SELECT COUNT(*) AS n FROM crypto_threat_entity_addresses
            WHERE entity_type = 'CLUSTER' AND entity_id = :cluster_id
        """), {"cluster_id": cluster_id}).mappings().first()
        self.db.execute(text("""
            UPDATE crypto_fraud_clusters SET member_count = :n WHERE id = :cluster_id
        """), {"n": int(count_row["n"]) if count_row else 0, "cluster_id": cluster_id})
        try:
            self.db.commit()
        except Exception:
            pass

    # ------------------------------------------------------------
    # Shared entity <-> address linking
    # ------------------------------------------------------------

    def link_address(
        self, *, entity_type: str, entity_id: int, address: str, chain: str,
        role: Optional[str] = None, evidence: Optional[Dict[str, Any]] = None,
    ) -> None:
        if entity_type not in VALID_ENTITY_TYPES:
            raise ValueError(f"Invalid entity_type: {entity_type}. Must be one of {VALID_ENTITY_TYPES}.")

        self.ensure_tables()
        if self.db is None:
            return

        # Avoid duplicate links for the same entity/address pair --
        # re-running discovery or clustering shouldn't pile up
        # repeated rows for something already linked.
        existing = self.db.execute(text("""
            SELECT id FROM crypto_threat_entity_addresses
            WHERE entity_type = :entity_type AND entity_id = :entity_id AND address = :address
        """), {"entity_type": entity_type, "entity_id": entity_id, "address": address.lower()}).mappings().first()
        if existing:
            return

        self.db.execute(text("""
            INSERT INTO crypto_threat_entity_addresses (entity_type, entity_id, address, chain, role, evidence)
            VALUES (:entity_type, :entity_id, :address, :chain, :role, :evidence)
        """), {
            "entity_type": entity_type, "entity_id": entity_id, "address": address.lower(),
            "chain": chain, "role": role, "evidence": json.dumps(evidence or {}),
        })
        try:
            self.db.commit()
        except Exception:
            pass

        if entity_type == "CLUSTER":
            self.update_cluster_member_count(entity_id)

    def list_addresses_for_entity(self, entity_type: str, entity_id: int) -> List[Dict[str, Any]]:
        self.ensure_tables()
        if self.db is None:
            return []
        rows = self.db.execute(text("""
            SELECT * FROM crypto_threat_entity_addresses
            WHERE entity_type = :entity_type AND entity_id = :entity_id
            ORDER BY linked_at ASC
        """), {"entity_type": entity_type, "entity_id": entity_id}).mappings().all()
        results = []
        for row in rows:
            item = dict(row)
            if item.get("evidence"):
                try:
                    item["evidence"] = json.loads(item["evidence"])
                except Exception:
                    pass
            results.append(item)
        return results

    def list_entities_for_address(self, address: str) -> List[Dict[str, Any]]:
        self.ensure_tables()
        if self.db is None or not address:
            return []
        rows = self.db.execute(text("""
            SELECT * FROM crypto_threat_entity_addresses WHERE address = :address
        """), {"address": address.lower()}).mappings().all()
        return [dict(row) for row in rows]

    # ------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------

    def _last_insert_id(self, table: str) -> int:
        dialect = _dialect_name(self.db)
        if dialect == "sqlite":
            row = self.db.execute(text("SELECT last_insert_rowid() AS id")).mappings().first()
        else:
            row = self.db.execute(text(f"SELECT MAX(id) AS id FROM {table}")).mappings().first()
        return int(row["id"]) if row and row["id"] is not None else -1


_REPOSITORY: Optional[CryptoThreatIntelligenceRepository] = None


def get_crypto_threat_intelligence_repository(db=None) -> CryptoThreatIntelligenceRepository:
    """
    Always constructs a fresh instance, same rationale as
    get_crypto_wallet_intelligence_repository(): cheap construction,
    and this session confirmed stale-cached-db singleton factories are
    a real, recurring bug class in this codebase.
    """
    return CryptoThreatIntelligenceRepository(db=db)