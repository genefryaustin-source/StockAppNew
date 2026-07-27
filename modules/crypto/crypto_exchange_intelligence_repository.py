"""
modules/crypto/crypto_exchange_intelligence_repository.py

Sprint CR-3: Exchange Intelligence.

- crypto_exchange_risk_scores: a refreshable cache of CoinGecko's
  /exchanges data (trust_score, trust_score_rank, 24h BTC volume,
  country, year established) -- the same free, no-key endpoint this
  app already uses elsewhere for market data.
- crypto_exchange_liquidity_snapshots: per-pair ticker-level liquidity
  (bid/ask spread, cost to move price up/down by a fixed amount),
  from CoinGecko's /exchanges/{id}/tickers -- a genuine liquidity
  signal, not a re-labeling of raw volume.
- crypto_exchange_reserve_addresses: analyst-entered wallet addresses
  believed to hold an exchange's reserves, each REQUIRING a source_url
  -- confirmed no free API (CoinGecko or DefiLlama) exposes this data
  directly, so this has to be human-sourced and human-verifiable, the
  same principle already applied to CR-2's Threat Actors/Campaigns.
- crypto_exchange_reserve_balance_history: periodic on-chain balance
  snapshots for each reserve address, to detect significant outflows
  over time (a real "bank run" early-warning signal).

Follows the same dialect-aware ensure_tables() pattern established
across CR-1 and CR-2.
"""

from __future__ import annotations

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


class CryptoExchangeIntelligenceRepository:
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
            CREATE TABLE IF NOT EXISTS crypto_exchange_risk_scores (
                exchange_id VARCHAR(100) PRIMARY KEY,
                name VARCHAR(200),
                trust_score DOUBLE PRECISION,
                trust_score_rank INTEGER,
                trade_volume_24h_btc DOUBLE PRECISION,
                country VARCHAR(100),
                year_established INTEGER,
                cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

        self.db.execute(text(f"""
            CREATE TABLE IF NOT EXISTS crypto_exchange_liquidity_snapshots (
                {id_column},
                exchange_id VARCHAR(100) NOT NULL,
                base VARCHAR(30),
                target VARCHAR(30),
                bid_ask_spread_percentage DOUBLE PRECISION,
                cost_to_move_up_usd DOUBLE PRECISION,
                cost_to_move_down_usd DOUBLE PRECISION,
                volume DOUBLE PRECISION,
                checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

        self.db.execute(text(f"""
            CREATE TABLE IF NOT EXISTS crypto_exchange_reserve_addresses (
                {id_column},
                tenant_id VARCHAR(100),
                exchange_name VARCHAR(200) NOT NULL,
                address VARCHAR(128) NOT NULL,
                chain VARCHAR(50) NOT NULL,
                source_url VARCHAR(500) NOT NULL,
                source_note TEXT,
                added_by VARCHAR(100),
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

        self.db.execute(text(f"""
            CREATE TABLE IF NOT EXISTS crypto_exchange_reserve_balance_history (
                {id_column},
                reserve_address_id INTEGER NOT NULL,
                balance_native DOUBLE PRECISION,
                checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

        try:
            self.db.commit()
        except Exception:
            pass

        self._tables_ready = True

    # ------------------------------------------------------------
    # Exchange risk scores
    # ------------------------------------------------------------

    def replace_exchange_risk_scores(self, rows: List[Dict[str, Any]]) -> int:
        """
        Wholesale replace, same rationale as the sanctions cache in
        CR-1: CoinGecko's /exchanges response is a full snapshot each
        time, so a full replace keeps this in sync (an exchange that
        drops off CoinGecko's tracked list -- e.g. delisted for fake
        volume -- naturally disappears here too).
        """
        self.ensure_tables()
        if self.db is None:
            return 0

        self.db.execute(text("DELETE FROM crypto_exchange_risk_scores"))

        inserted = 0
        for row in rows:
            exchange_id = row.get("id")
            if not exchange_id:
                continue
            self.db.execute(text("""
                INSERT INTO crypto_exchange_risk_scores (
                    exchange_id, name, trust_score, trust_score_rank,
                    trade_volume_24h_btc, country, year_established
                ) VALUES (
                    :exchange_id, :name, :trust_score, :trust_score_rank,
                    :trade_volume_24h_btc, :country, :year_established
                )
            """), {
                "exchange_id": exchange_id,
                "name": row.get("name"),
                "trust_score": row.get("trust_score"),
                "trust_score_rank": row.get("trust_score_rank"),
                "trade_volume_24h_btc": row.get("trade_volume_24h_btc"),
                "country": row.get("country"),
                "year_established": row.get("year_established"),
            })
            inserted += 1

        try:
            self.db.commit()
        except Exception:
            pass

        return inserted

    def list_exchange_risk_scores(self, *, limit: int = 250) -> List[Dict[str, Any]]:
        self.ensure_tables()
        if self.db is None:
            return []
        rows = self.db.execute(text("""
            SELECT * FROM crypto_exchange_risk_scores
            ORDER BY trust_score_rank ASC NULLS LAST
            LIMIT :limit
        """), {"limit": limit}).mappings().all()
        return [dict(row) for row in rows]

    def get_exchange_risk_score(self, exchange_id: str) -> Optional[Dict[str, Any]]:
        self.ensure_tables()
        if self.db is None:
            return None
        row = self.db.execute(text("""
            SELECT * FROM crypto_exchange_risk_scores WHERE exchange_id = :exchange_id
        """), {"exchange_id": exchange_id}).mappings().first()
        return dict(row) if row else None

    def risk_scores_last_cached_at(self) -> Optional[datetime]:
        self.ensure_tables()
        if self.db is None:
            return None
        row = self.db.execute(text(
            "SELECT MAX(cached_at) AS latest FROM crypto_exchange_risk_scores"
        )).mappings().first()
        return row["latest"] if row else None

    # ------------------------------------------------------------
    # Liquidity snapshots
    # ------------------------------------------------------------

    def add_liquidity_snapshot(
        self, *, exchange_id: str, base: str, target: str,
        bid_ask_spread_percentage: Optional[float], cost_to_move_up_usd: Optional[float],
        cost_to_move_down_usd: Optional[float], volume: Optional[float],
    ) -> None:
        self.ensure_tables()
        if self.db is None:
            return
        self.db.execute(text("""
            INSERT INTO crypto_exchange_liquidity_snapshots (
                exchange_id, base, target, bid_ask_spread_percentage,
                cost_to_move_up_usd, cost_to_move_down_usd, volume
            ) VALUES (
                :exchange_id, :base, :target, :spread, :up, :down, :volume
            )
        """), {
            "exchange_id": exchange_id, "base": base, "target": target,
            "spread": bid_ask_spread_percentage, "up": cost_to_move_up_usd,
            "down": cost_to_move_down_usd, "volume": volume,
        })
        try:
            self.db.commit()
        except Exception:
            pass

    def list_latest_liquidity_snapshots(self, exchange_id: str) -> List[Dict[str, Any]]:
        """
        Most recent snapshot per (base, target) pair for the given
        exchange -- not every historical row, just the latest reading
        for each pair.
        """
        self.ensure_tables()
        if self.db is None:
            return []
        rows = self.db.execute(text("""
            SELECT s.* FROM crypto_exchange_liquidity_snapshots s
            INNER JOIN (
                SELECT base, target, MAX(checked_at) AS max_checked_at
                FROM crypto_exchange_liquidity_snapshots
                WHERE exchange_id = :exchange_id
                GROUP BY base, target
            ) latest
            ON s.base = latest.base AND s.target = latest.target AND s.checked_at = latest.max_checked_at
            WHERE s.exchange_id = :exchange_id
            ORDER BY s.bid_ask_spread_percentage ASC NULLS LAST
        """), {"exchange_id": exchange_id}).mappings().all()
        return [dict(row) for row in rows]

    # ------------------------------------------------------------
    # Reserve addresses (analyst-entered, source-required)
    # ------------------------------------------------------------

    def add_reserve_address(
        self, *, tenant_id: Optional[str], exchange_name: str, address: str, chain: str,
        source_url: str, source_note: Optional[str] = None, added_by: Optional[str] = None,
    ) -> int:
        if not source_url or not source_url.strip():
            raise ValueError(
                "source_url is required -- reserve addresses must be traceable to where "
                "they were confirmed, the same principle already applied to Threat Actor "
                "and Campaign attribution."
            )

        self.ensure_tables()
        self.db.execute(text("""
            INSERT INTO crypto_exchange_reserve_addresses (
                tenant_id, exchange_name, address, chain, source_url, source_note, added_by
            ) VALUES (
                :tenant_id, :exchange_name, :address, :chain, :source_url, :source_note, :added_by
            )
        """), {
            "tenant_id": tenant_id, "exchange_name": exchange_name, "address": address.lower(),
            "chain": chain, "source_url": source_url.strip(), "source_note": source_note, "added_by": added_by,
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
                "SELECT id FROM crypto_exchange_reserve_addresses WHERE address = :address ORDER BY added_at DESC LIMIT 1"
            ), {"address": address.lower()}).mappings().first()
        return int(row["id"]) if row and row["id"] is not None else -1

    def list_reserve_addresses(self, *, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
        self.ensure_tables()
        if self.db is None:
            return []
        clauses, params = [], {}
        if tenant_id is not None:
            clauses.append("tenant_id = :tenant_id")
            params["tenant_id"] = tenant_id
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.db.execute(text(f"""
            SELECT * FROM crypto_exchange_reserve_addresses {where_sql} ORDER BY exchange_name, added_at
        """), params).mappings().all()
        return [dict(row) for row in rows]

    def record_reserve_balance(self, reserve_address_id: int, balance_native: float) -> None:
        self.ensure_tables()
        if self.db is None:
            return
        self.db.execute(text("""
            INSERT INTO crypto_exchange_reserve_balance_history (reserve_address_id, balance_native)
            VALUES (:reserve_address_id, :balance_native)
        """), {"reserve_address_id": reserve_address_id, "balance_native": balance_native})
        try:
            self.db.commit()
        except Exception:
            pass

    def get_reserve_balance_history(self, reserve_address_id: int, *, limit: int = 100) -> List[Dict[str, Any]]:
        self.ensure_tables()
        if self.db is None:
            return []
        rows = self.db.execute(text("""
            SELECT * FROM crypto_exchange_reserve_balance_history
            WHERE reserve_address_id = :reserve_address_id
            ORDER BY checked_at DESC, id DESC
            LIMIT :limit
        """), {"reserve_address_id": reserve_address_id, "limit": limit}).mappings().all()
        return [dict(row) for row in rows]

    def get_latest_reserve_balance(self, reserve_address_id: int) -> Optional[Dict[str, Any]]:
        history = self.get_reserve_balance_history(reserve_address_id, limit=1)
        return history[0] if history else None


_REPOSITORY: Optional[CryptoExchangeIntelligenceRepository] = None


def get_crypto_exchange_intelligence_repository(db=None) -> CryptoExchangeIntelligenceRepository:
    return CryptoExchangeIntelligenceRepository(db=db)