"""
modules/crypto/crypto_defi_intelligence_repository.py

Sprint CR-4: DeFi Intelligence.

- crypto_defi_protocol_tvl_history: time-series TVL snapshots per
  protocol, to detect significant declines over time.
- crypto_defi_protocol_risk_flags: risk signals for a protocol --
  TVL_DECLINE (computed locally from the history above, always
  available) and HACK_HISTORY (from DefiLlama's hacks dataset, whose
  free-vs-paid status is genuinely unconfirmed from this sandbox --
  see crypto_defi_service.py's fetch_hacks() for how this is handled
  defensively).
- crypto_defi_liquidity_pools_cache: a refreshable cache of
  DefiLlama's /pools data (APY, TVL per pool) -- DefiLlama's own
  official docs list this as free, though one third-party source
  disputes it; handled defensively at the fetch layer.
- crypto_defi_bridge_volume_cache: a refreshable cache of bridge
  volume data -- DefiLlama's official docs list detailed bridge data
  as Pro-only; this table may legitimately stay empty if that's
  confirmed true in the deployed environment, which is an honest
  outcome, not a bug.

Follows the same dialect-aware ensure_tables() pattern established
across CR-1, CR-2, and CR-3.
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


class CryptoDefiIntelligenceRepository:
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
            CREATE TABLE IF NOT EXISTS crypto_defi_protocol_tvl_history (
                {id_column},
                protocol_slug VARCHAR(150) NOT NULL,
                tvl_usd DOUBLE PRECISION,
                checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

        self.db.execute(text(f"""
            CREATE TABLE IF NOT EXISTS crypto_defi_protocol_risk_flags (
                {id_column},
                protocol_slug VARCHAR(150) NOT NULL,
                risk_type VARCHAR(50) NOT NULL,
                severity VARCHAR(20),
                details TEXT,
                flagged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

        self.db.execute(text(f"""
            CREATE TABLE IF NOT EXISTS crypto_defi_liquidity_pools_cache (
                {id_column},
                pool_id VARCHAR(150),
                project VARCHAR(150),
                chain VARCHAR(50),
                symbol VARCHAR(100),
                tvl_usd DOUBLE PRECISION,
                apy DOUBLE PRECISION,
                cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

        self.db.execute(text(f"""
            CREATE TABLE IF NOT EXISTS crypto_defi_bridge_volume_cache (
                {id_column},
                bridge_name VARCHAR(150),
                chain VARCHAR(50),
                volume_24h_usd DOUBLE PRECISION,
                cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

        try:
            self.db.commit()
        except Exception:
            pass

        self._tables_ready = True

    # ------------------------------------------------------------
    # TVL history
    # ------------------------------------------------------------

    def record_tvl(self, protocol_slug: str, tvl_usd: float) -> None:
        self.ensure_tables()
        if self.db is None:
            return
        self.db.execute(text("""
            INSERT INTO crypto_defi_protocol_tvl_history (protocol_slug, tvl_usd)
            VALUES (:protocol_slug, :tvl_usd)
        """), {"protocol_slug": protocol_slug, "tvl_usd": tvl_usd})
        try:
            self.db.commit()
        except Exception:
            pass

    def get_tvl_history(self, protocol_slug: str, *, limit: int = 100) -> List[Dict[str, Any]]:
        self.ensure_tables()
        if self.db is None:
            return []
        rows = self.db.execute(text("""
            SELECT * FROM crypto_defi_protocol_tvl_history
            WHERE protocol_slug = :protocol_slug
            ORDER BY checked_at DESC, id DESC
            LIMIT :limit
        """), {"protocol_slug": protocol_slug, "limit": limit}).mappings().all()
        return [dict(row) for row in rows]

    def get_latest_tvl(self, protocol_slug: str) -> Optional[Dict[str, Any]]:
        history = self.get_tvl_history(protocol_slug, limit=1)
        return history[0] if history else None

    # ------------------------------------------------------------
    # Risk flags
    # ------------------------------------------------------------

    def add_risk_flag(
        self, *, protocol_slug: str, risk_type: str, severity: str, details: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.ensure_tables()
        if self.db is None:
            return
        self.db.execute(text("""
            INSERT INTO crypto_defi_protocol_risk_flags (protocol_slug, risk_type, severity, details)
            VALUES (:protocol_slug, :risk_type, :severity, :details)
        """), {
            "protocol_slug": protocol_slug, "risk_type": risk_type,
            "severity": severity, "details": json.dumps(details or {}),
        })
        try:
            self.db.commit()
        except Exception:
            pass

    def list_risk_flags(self, protocol_slug: Optional[str] = None, *, limit: int = 200) -> List[Dict[str, Any]]:
        self.ensure_tables()
        if self.db is None:
            return []
        clauses, params = [], {"limit": limit}
        if protocol_slug is not None:
            clauses.append("protocol_slug = :protocol_slug")
            params["protocol_slug"] = protocol_slug
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.db.execute(text(f"""
            SELECT * FROM crypto_defi_protocol_risk_flags {where_sql}
            ORDER BY flagged_at DESC LIMIT :limit
        """), params).mappings().all()
        results = []
        for row in rows:
            item = dict(row)
            if item.get("details"):
                try:
                    item["details"] = json.loads(item["details"])
                except Exception:
                    pass
            results.append(item)
        return results

    # ------------------------------------------------------------
    # Liquidity pools cache
    # ------------------------------------------------------------

    def replace_liquidity_pools(self, rows: List[Dict[str, Any]]) -> int:
        self.ensure_tables()
        if self.db is None:
            return 0
        self.db.execute(text("DELETE FROM crypto_defi_liquidity_pools_cache"))
        inserted = 0
        for row in rows:
            self.db.execute(text("""
                INSERT INTO crypto_defi_liquidity_pools_cache (pool_id, project, chain, symbol, tvl_usd, apy)
                VALUES (:pool_id, :project, :chain, :symbol, :tvl_usd, :apy)
            """), {
                "pool_id": row.get("pool_id"), "project": row.get("project"), "chain": row.get("chain"),
                "symbol": row.get("symbol"), "tvl_usd": row.get("tvl_usd"), "apy": row.get("apy"),
            })
            inserted += 1
        try:
            self.db.commit()
        except Exception:
            pass
        return inserted

    def list_liquidity_pools(self, *, chain: Optional[str] = None, limit: int = 250) -> List[Dict[str, Any]]:
        self.ensure_tables()
        if self.db is None:
            return []
        clauses, params = [], {"limit": limit}
        if chain is not None:
            clauses.append("chain = :chain")
            params["chain"] = chain
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.db.execute(text(f"""
            SELECT * FROM crypto_defi_liquidity_pools_cache {where_sql}
            ORDER BY tvl_usd DESC NULLS LAST LIMIT :limit
        """), params).mappings().all()
        return [dict(row) for row in rows]

    def liquidity_pools_last_cached_at(self) -> Optional[datetime]:
        self.ensure_tables()
        if self.db is None:
            return None
        row = self.db.execute(text(
            "SELECT MAX(cached_at) AS latest FROM crypto_defi_liquidity_pools_cache"
        )).mappings().first()
        return row["latest"] if row else None

    # ------------------------------------------------------------
    # Bridge volume cache
    # ------------------------------------------------------------

    def replace_bridge_volumes(self, rows: List[Dict[str, Any]]) -> int:
        self.ensure_tables()
        if self.db is None:
            return 0
        self.db.execute(text("DELETE FROM crypto_defi_bridge_volume_cache"))
        inserted = 0
        for row in rows:
            self.db.execute(text("""
                INSERT INTO crypto_defi_bridge_volume_cache (bridge_name, chain, volume_24h_usd)
                VALUES (:bridge_name, :chain, :volume_24h_usd)
            """), {
                "bridge_name": row.get("bridge_name"), "chain": row.get("chain"),
                "volume_24h_usd": row.get("volume_24h_usd"),
            })
            inserted += 1
        try:
            self.db.commit()
        except Exception:
            pass
        return inserted

    def list_bridge_volumes(self, *, limit: int = 250) -> List[Dict[str, Any]]:
        self.ensure_tables()
        if self.db is None:
            return []
        rows = self.db.execute(text("""
            SELECT * FROM crypto_defi_bridge_volume_cache
            ORDER BY volume_24h_usd DESC NULLS LAST LIMIT :limit
        """), {"limit": limit}).mappings().all()
        return [dict(row) for row in rows]

    def bridge_volumes_last_cached_at(self) -> Optional[datetime]:
        self.ensure_tables()
        if self.db is None:
            return None
        row = self.db.execute(text(
            "SELECT MAX(cached_at) AS latest FROM crypto_defi_bridge_volume_cache"
        )).mappings().first()
        return row["latest"] if row else None


_REPOSITORY: Optional[CryptoDefiIntelligenceRepository] = None


def get_crypto_defi_intelligence_repository(db=None) -> CryptoDefiIntelligenceRepository:
    return CryptoDefiIntelligenceRepository(db=db)