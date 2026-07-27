"""
modules/crypto/crypto_wallet_intelligence_repository.py

Sprint CR-1: Autonomous Wallet Intelligence

Owns persistence for:
- crypto_wallet_risk_flags: wallets flagged for sanction/mixer/scam/
  rug-pull exposure, whether discovered automatically (via known-bad
  counterparty monitoring) or looked up manually.
- crypto_sanctioned_addresses: a local cache of OFAC's published
  crypto addresses, refreshed periodically rather than re-fetched
  (and re-parsed) on every check -- the source XML is tens of MB.
- crypto_wallet_intel_settings: per-tenant configuration, in
  particular which risk-data provider is active (built-in free
  sources, or a Tenant Admin-configured premium provider such as
  Chainalysis/TRM Labs).

Follows the same dialect-aware ensure_tables() pattern used
throughout this app (see execution_order_repository.py) rather than
assuming Postgres or SQLite syntax.
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
    """Best-effort detection of the SQLAlchemy dialect (postgresql/sqlite/...)."""
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


class CryptoWalletIntelligenceRepository:
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
            CREATE TABLE IF NOT EXISTS crypto_wallet_risk_flags (
                {id_column},
                tenant_id VARCHAR(100),
                address VARCHAR(128) NOT NULL,
                chain VARCHAR(50) NOT NULL,
                exposure_type VARCHAR(30) NOT NULL,
                severity VARCHAR(20),
                source VARCHAR(50),
                evidence TEXT,
                discovered_via_address VARCHAR(128),
                discovered_via_tx VARCHAR(128),
                status VARCHAR(20) DEFAULT 'ACTIVE',
                first_seen_at TIMESTAMP,
                last_checked_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

        self.db.execute(text("""
            CREATE TABLE IF NOT EXISTS crypto_sanctioned_addresses (
                address VARCHAR(128) PRIMARY KEY,
                chain_asset VARCHAR(20),
                program VARCHAR(150),
                entity_name VARCHAR(255),
                source_list_date VARCHAR(40),
                cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

        self.db.execute(text(f"""
            CREATE TABLE IF NOT EXISTS crypto_wallet_intel_settings (
                {id_column},
                tenant_id VARCHAR(100) NOT NULL,
                active_provider VARCHAR(50) DEFAULT 'free',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

        self.db.execute(text(f"""
            CREATE TABLE IF NOT EXISTS crypto_wallet_intel_scheduler_heartbeat (
                {id_column},
                job_name VARCHAR(50) NOT NULL,
                status VARCHAR(20),
                message TEXT,
                last_run_at TIMESTAMP,
                last_success_at TIMESTAMP
            )
        """))

        try:
            self.db.commit()
        except Exception:
            pass

        self._tables_ready = True

    # ------------------------------------------------------------
    # Risk flags
    # ------------------------------------------------------------

    def add_flag(
        self,
        *,
        tenant_id: Optional[str],
        address: str,
        chain: str,
        exposure_type: str,
        severity: str,
        source: str,
        evidence: Optional[Dict[str, Any]] = None,
        discovered_via_address: Optional[str] = None,
        discovered_via_tx: Optional[str] = None,
    ) -> None:
        self.ensure_tables()
        if self.db is None:
            return

        now = _utc_now_naive()
        self.db.execute(text("""
            INSERT INTO crypto_wallet_risk_flags (
                tenant_id, address, chain, exposure_type, severity, source,
                evidence, discovered_via_address, discovered_via_tx,
                status, first_seen_at, last_checked_at
            ) VALUES (
                :tenant_id, :address, :chain, :exposure_type, :severity, :source,
                :evidence, :discovered_via_address, :discovered_via_tx,
                'ACTIVE', :now, :now
            )
        """), {
            "tenant_id": tenant_id,
            "address": address.lower() if address else address,
            "chain": chain,
            "exposure_type": exposure_type,
            "severity": severity,
            "source": source,
            "evidence": json.dumps(evidence or {}),
            "discovered_via_address": discovered_via_address,
            "discovered_via_tx": discovered_via_tx,
            "now": now,
        })
        try:
            self.db.commit()
        except Exception:
            pass

    def list_flags(
        self, *, tenant_id: Optional[str] = None, exposure_type: Optional[str] = None, limit: int = 200,
    ) -> List[Dict[str, Any]]:
        self.ensure_tables()
        if self.db is None:
            return []

        clauses = ["status = 'ACTIVE'"]
        params: Dict[str, Any] = {"limit": limit}
        if tenant_id is not None:
            clauses.append("tenant_id = :tenant_id")
            params["tenant_id"] = tenant_id
        if exposure_type is not None:
            clauses.append("exposure_type = :exposure_type")
            params["exposure_type"] = exposure_type

        where_sql = " AND ".join(clauses)
        rows = self.db.execute(text(f"""
            SELECT * FROM crypto_wallet_risk_flags
            WHERE {where_sql}
            ORDER BY first_seen_at DESC
            LIMIT :limit
        """), params).mappings().all()

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

    def has_flag(self, *, address: str, exposure_type: Optional[str] = None) -> bool:
        self.ensure_tables()
        if self.db is None or not address:
            return False

        clauses = ["address = :address", "status = 'ACTIVE'"]
        params: Dict[str, Any] = {"address": address.lower()}
        if exposure_type is not None:
            clauses.append("exposure_type = :exposure_type")
            params["exposure_type"] = exposure_type

        where_sql = " AND ".join(clauses)
        row = self.db.execute(text(f"""
            SELECT 1 FROM crypto_wallet_risk_flags WHERE {where_sql} LIMIT 1
        """), params).fetchone()
        return row is not None

    # ------------------------------------------------------------
    # Sanctions cache
    # ------------------------------------------------------------

    def replace_sanctioned_addresses(self, rows: List[Dict[str, Any]]) -> int:
        """
        Replaces the local sanctions cache wholesale -- OFAC publishes a
        full snapshot each refresh (not a diff), so a full replace is
        the correct, simplest way to stay in sync: addresses that were
        delisted (e.g. Tornado Cash in March 2025) are naturally
        removed rather than lingering forever.
        """
        self.ensure_tables()
        if self.db is None:
            return 0

        self.db.execute(text("DELETE FROM crypto_sanctioned_addresses"))

        inserted = 0
        for row in rows:
            address = (row.get("address") or "").strip()
            if not address:
                continue
            try:
                self.db.execute(text("""
                    INSERT INTO crypto_sanctioned_addresses (
                        address, chain_asset, program, entity_name, source_list_date
                    ) VALUES (
                        :address, :chain_asset, :program, :entity_name, :source_list_date
                    )
                    ON CONFLICT (address) DO NOTHING
                """), {
                    "address": address.lower(),
                    "chain_asset": row.get("asset"),
                    "program": row.get("program"),
                    "entity_name": row.get("entity_name"),
                    "source_list_date": row.get("source_list_date"),
                })
                inserted += 1
            except Exception:
                # ON CONFLICT syntax differs across dialects for
                # composite/no-unique-constraint edge cases -- skip a
                # bad row rather than abort the whole refresh.
                continue

        try:
            self.db.commit()
        except Exception:
            pass

        return inserted

    def is_sanctioned(self, address: str) -> Optional[Dict[str, Any]]:
        self.ensure_tables()
        if self.db is None or not address:
            return None
        row = self.db.execute(text("""
            SELECT * FROM crypto_sanctioned_addresses WHERE address = :address
        """), {"address": address.lower()}).mappings().first()
        return dict(row) if row else None

    def sanctioned_count(self) -> int:
        self.ensure_tables()
        if self.db is None:
            return 0
        row = self.db.execute(text("SELECT COUNT(*) AS n FROM crypto_sanctioned_addresses")).mappings().first()
        return int(row["n"]) if row else 0

    def sanctions_last_cached_at(self) -> Optional[datetime]:
        self.ensure_tables()
        if self.db is None:
            return None
        row = self.db.execute(text(
            "SELECT MAX(cached_at) AS latest FROM crypto_sanctioned_addresses"
        )).mappings().first()
        return row["latest"] if row else None

    # ------------------------------------------------------------
    # Tenant provider settings
    # ------------------------------------------------------------

    def get_active_provider(self, tenant_id: str) -> str:
        self.ensure_tables()
        if self.db is None or not tenant_id:
            return "free"
        row = self.db.execute(text("""
            SELECT active_provider FROM crypto_wallet_intel_settings WHERE tenant_id = :tenant_id
        """), {"tenant_id": tenant_id}).mappings().first()
        return row["active_provider"] if row else "free"

    def set_active_provider(self, tenant_id: str, provider: str) -> None:
        self.ensure_tables()
        if self.db is None or not tenant_id:
            return

        existing = self.db.execute(text("""
            SELECT id FROM crypto_wallet_intel_settings WHERE tenant_id = :tenant_id
        """), {"tenant_id": tenant_id}).mappings().first()

        now = _utc_now_naive()
        if existing:
            self.db.execute(text("""
                UPDATE crypto_wallet_intel_settings
                SET active_provider = :provider, updated_at = :now
                WHERE tenant_id = :tenant_id
            """), {"provider": provider, "now": now, "tenant_id": tenant_id})
        else:
            self.db.execute(text("""
                INSERT INTO crypto_wallet_intel_settings (tenant_id, active_provider, updated_at)
                VALUES (:tenant_id, :provider, :now)
            """), {"tenant_id": tenant_id, "provider": provider, "now": now})

        try:
            self.db.commit()
        except Exception:
            pass

    # ------------------------------------------------------------
    # Scheduler heartbeat
    # ------------------------------------------------------------

    def record_job_heartbeat(self, job_name: str, *, status: str, message: Optional[str] = None) -> None:
        """
        Upserts a single heartbeat row per job_name -- a background
        thread's in-memory running/stopped state isn't visible to a
        separate Streamlit session or process looking at the UI, but a
        DB row is, matching the same "heartbeat" concept already used
        by PortfolioScheduler elsewhere in this app.
        """
        self.ensure_tables()
        if self.db is None:
            return

        now = _utc_now_naive()
        existing = self.db.execute(text("""
            SELECT id FROM crypto_wallet_intel_scheduler_heartbeat WHERE job_name = :job_name
        """), {"job_name": job_name}).mappings().first()

        if existing:
            self.db.execute(text("""
                UPDATE crypto_wallet_intel_scheduler_heartbeat
                SET status = :status, message = :message, last_run_at = :now,
                    last_success_at = CASE WHEN :status = 'ok' THEN :now ELSE last_success_at END
                WHERE job_name = :job_name
            """), {"status": status, "message": message, "now": now, "job_name": job_name})
        else:
            self.db.execute(text("""
                INSERT INTO crypto_wallet_intel_scheduler_heartbeat (
                    job_name, status, message, last_run_at, last_success_at
                ) VALUES (
                    :job_name, :status, :message, :now, :success_at
                )
            """), {
                "job_name": job_name, "status": status, "message": message, "now": now,
                "success_at": now if status == "ok" else None,
            })

        try:
            self.db.commit()
        except Exception:
            pass

    def get_job_heartbeat(self, job_name: str) -> Optional[Dict[str, Any]]:
        self.ensure_tables()
        if self.db is None:
            return None
        row = self.db.execute(text("""
            SELECT * FROM crypto_wallet_intel_scheduler_heartbeat WHERE job_name = :job_name
        """), {"job_name": job_name}).mappings().first()
        return dict(row) if row else None


def get_crypto_wallet_intelligence_repository(db=None) -> CryptoWalletIntelligenceRepository:
    """
    Always constructs a fresh instance when a db is supplied, rather
    than caching a module-level singleton -- confirmed this exact
    session that stale-cached-db factories are a real, recurring bug
    class in this codebase (get_forex_order_management_engine,
    get_forex_autonomous_trader, and others all had it). Construction
    here is cheap (attribute assignment only; ensure_tables() is
    itself idempotent and guarded), so there's no performance reason
    to share an instance across calls.
    """
    return CryptoWalletIntelligenceRepository(db=db)