from __future__ import annotations

import json
import re
import uuid
from typing import Iterable

import pandas as pd
from sqlalchemy import text

from modules.universe.symbol_validator import normalize_symbol


EXCHANGE_NAME_ALIASES = {
    "NASDAQ STOCKS": "NASDAQ",
    "NASDAQ": "NASDAQ",
    "NYSE STOCKS": "NYSE",
    "NYSE": "NYSE",
    "AMEX STOCKS": "AMEX",
    "AMEX": "AMEX",
    "S&P 500": "SP500",
    "S&P  500": "SP500",
    "SP500": "SP500",
    "S&P500": "SP500",
}


class UniverseExchangeSyncService:
    """
    Tenant-scoped exchange membership sync service.

    This service compares a selected tenant universe against available
    exchange/reference data already loaded in the database.
    """

    def __init__(self, db):
        self.db = db
        self._ensure_tables()

    def _rollback(self) -> None:
        try:
            self.db.rollback()
        except Exception:
            pass

    def _ensure_tables(self) -> None:
        try:
            self.db.execute(text("""
                CREATE TABLE IF NOT EXISTS universe_sync_history (
                    id VARCHAR(64) PRIMARY KEY,
                    tenant_id VARCHAR(100) NOT NULL,
                    universe_id VARCHAR(100) NOT NULL,
                    reference_source VARCHAR(120),
                    added_count INTEGER DEFAULT 0,
                    removed_count INTEGER DEFAULT 0,
                    added_symbols TEXT,
                    removed_symbols TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            self.db.commit()
        except Exception:
            self._rollback()
            raise

    @staticmethod
    def _normalize_name(value: str | None) -> str:
        if not value:
            return ""
        cleaned = re.sub(r"\s+", " ", str(value).strip().upper())
        return EXCHANGE_NAME_ALIASES.get(cleaned, cleaned)

    @staticmethod
    def _clean_symbols(symbols: Iterable[str]) -> list[str]:
        out = set()
        for sym in symbols:
            try:
                clean = normalize_symbol(str(sym))
                if clean:
                    out.add(clean.upper().strip())
            except Exception:
                continue
        return sorted(out)

    def _fetch_symbols_from_query(self, sql: str, params: dict) -> list[str]:
        rows = self.db.execute(text(sql), params).fetchall()
        return self._clean_symbols([r[0] for r in rows if r and r[0]])

    def get_universe(self, tenant_id: str, universe_id: str) -> dict | None:
        try:
            row = self.db.execute(text("""
                SELECT id, tenant_id, name
                FROM universes
                WHERE id = :universe_id
                  AND tenant_id = :tenant_id
                LIMIT 1
            """), {
                "tenant_id": tenant_id,
                "universe_id": universe_id,
            }).fetchone()

            if not row:
                return None

            return {
                "id": str(row.id),
                "tenant_id": str(row.tenant_id),
                "name": str(row.name),
                "reference_key": self._normalize_name(row.name),
            }

        except Exception:
            self._rollback()
            raise

    def get_current_symbols(self, tenant_id: str, universe_id: str) -> list[str]:
        try:
            return self._fetch_symbols_from_query("""
                SELECT DISTINCT symbol
                FROM universe_symbols
                WHERE tenant_id = :tenant_id
                  AND universe_id = :universe_id
                  AND symbol IS NOT NULL
            """, {
                "tenant_id": tenant_id,
                "universe_id": universe_id,
            })
        except Exception:
            self._rollback()
            raise

    def get_reference_symbols(
        self,
        tenant_id: str,
        selected_universe_id: str,
        reference_key: str | None = None,
    ) -> tuple[list[str], str]:
        universe = self.get_universe(tenant_id, selected_universe_id)
        if not universe:
            return [], "Unavailable"

        key = self._normalize_name(reference_key or universe["name"])

        # Try common exchange/reference tables. Each query is isolated because
        # not every deployment has every reference table/column.
        reference_queries = [
            (
                "universe_equities.exchange",
                """
                SELECT DISTINCT symbol
                FROM universe_equities
                WHERE tenant_id = :tenant_id
                  AND symbol IS NOT NULL
                  AND UPPER(TRIM(exchange)) = :key
                """,
                {"tenant_id": tenant_id, "key": key},
            ),
            (
                "universe_equities.universe_name",
                """
                SELECT DISTINCT symbol
                FROM universe_equities
                WHERE tenant_id = :tenant_id
                  AND symbol IS NOT NULL
                  AND UPPER(TRIM(universe_name)) = :name
                """,
                {"tenant_id": tenant_id, "name": universe["name"].upper().strip()},
            ),
            (
                "universe_equities.source",
                """
                SELECT DISTINCT symbol
                FROM universe_equities
                WHERE tenant_id = :tenant_id
                  AND symbol IS NOT NULL
                  AND UPPER(TRIM(source)) = :key
                """,
                {"tenant_id": tenant_id, "key": key},
            ),
            (
                "equities.exchange",
                """
                SELECT DISTINCT symbol
                FROM equities
                WHERE symbol IS NOT NULL
                  AND UPPER(TRIM(exchange)) = :key
                """,
                {"key": key},
            ),
            (
                "stocks.exchange",
                """
                SELECT DISTINCT symbol
                FROM stocks
                WHERE symbol IS NOT NULL
                  AND UPPER(TRIM(exchange)) = :key
                """,
                {"key": key},
            ),
            (
                "symbols.exchange",
                """
                SELECT DISTINCT symbol
                FROM symbols
                WHERE symbol IS NOT NULL
                  AND UPPER(TRIM(exchange)) = :key
                """,
                {"key": key},
            ),
        ]

        for label, sql, params in reference_queries:
            try:
                symbols = self._fetch_symbols_from_query(sql, params)
                if symbols:
                    return symbols, label
            except Exception:
                self._rollback()

        return self.get_current_symbols(tenant_id, selected_universe_id), "selected universe fallback"

    def preview_exchange_sync(
        self,
        tenant_id: str,
        universe_id: str,
        reference_key: str | None = None,
    ) -> dict:
        universe = self.get_universe(tenant_id, universe_id)
        if not universe:
            return {
                "ok": False,
                "message": "Universe not found for this tenant.",
                "current_count": 0,
                "reference_count": 0,
                "missing": [],
                "stale": [],
                "source": "Unavailable",
            }

        current = set(self.get_current_symbols(tenant_id, universe_id))
        reference, source = self.get_reference_symbols(
            tenant_id=tenant_id,
            selected_universe_id=universe_id,
            reference_key=reference_key,
        )
        reference_set = set(reference)

        missing = sorted(reference_set - current)
        stale = sorted(current - reference_set) if reference_set else []

        return {
            "ok": True,
            "message": "Preview complete.",
            "universe": universe,
            "current_count": len(current),
            "reference_count": len(reference_set),
            "missing_count": len(missing),
            "stale_count": len(stale),
            "missing": missing,
            "stale": stale,
            "source": source,
        }

    def add_missing_symbols(self, tenant_id: str, universe_id: str, symbols: list[str]) -> int:
        clean = self._clean_symbols(symbols)
        if not clean:
            return 0

        inserted = 0

        try:
            for sym in clean:
                result = self.db.execute(text("""
                    INSERT INTO universe_symbols
                    (
                        tenant_id,
                        universe_id,
                        symbol,
                        created_at
                    )
                    VALUES
                    (
                        :tenant_id,
                        :universe_id,
                        :symbol,
                        CURRENT_TIMESTAMP
                    )
                    ON CONFLICT DO NOTHING
                """), {
                    "tenant_id": tenant_id,
                    "universe_id": universe_id,
                    "symbol": sym,
                })
                inserted += result.rowcount or 0

            self.db.commit()
            return inserted

        except Exception:
            self._rollback()
            raise

    def remove_stale_symbols(self, tenant_id: str, universe_id: str, symbols: list[str]) -> int:
        clean = self._clean_symbols(symbols)
        if not clean:
            return 0

        try:
            result = self.db.execute(text("""
                DELETE FROM universe_symbols
                WHERE tenant_id = :tenant_id
                  AND universe_id = :universe_id
                  AND symbol = ANY(:symbols)
            """), {
                "tenant_id": tenant_id,
                "universe_id": universe_id,
                "symbols": clean,
            })

            removed = result.rowcount or 0
            self.db.commit()
            return removed

        except Exception:
            self._rollback()
            raise

    def sync_exchange_membership(
        self,
        tenant_id: str,
        universe_id: str,
        reference_key: str | None = None,
        add_missing: bool = True,
        remove_stale: bool = False,
    ) -> dict:
        preview = self.preview_exchange_sync(
            tenant_id=tenant_id,
            universe_id=universe_id,
            reference_key=reference_key,
        )

        if not preview.get("ok"):
            return preview

        missing = preview.get("missing", [])
        stale = preview.get("stale", [])

        added_count = self.add_missing_symbols(
            tenant_id=tenant_id,
            universe_id=universe_id,
            symbols=missing,
        ) if add_missing else 0

        removed_count = self.remove_stale_symbols(
            tenant_id=tenant_id,
            universe_id=universe_id,
            symbols=stale,
        ) if remove_stale else 0

        self.record_sync_history(
            tenant_id=tenant_id,
            universe_id=universe_id,
            source=preview.get("source", "Unknown"),
            added_symbols=missing if add_missing else [],
            removed_symbols=stale if remove_stale else [],
            added_count=added_count,
            removed_count=removed_count,
        )

        preview["added_count"] = added_count
        preview["removed_count"] = removed_count
        preview["synced"] = True

        return preview

    def record_sync_history(
        self,
        tenant_id: str,
        universe_id: str,
        source: str,
        added_symbols: list[str],
        removed_symbols: list[str],
        added_count: int,
        removed_count: int,
    ) -> None:
        try:
            self.db.execute(text("""
                INSERT INTO universe_sync_history
                (
                    id,
                    tenant_id,
                    universe_id,
                    reference_source,
                    added_count,
                    removed_count,
                    added_symbols,
                    removed_symbols,
                    created_at
                )
                VALUES
                (
                    :id,
                    :tenant_id,
                    :universe_id,
                    :reference_source,
                    :added_count,
                    :removed_count,
                    :added_symbols,
                    :removed_symbols,
                    CURRENT_TIMESTAMP
                )
            """), {
                "id": str(uuid.uuid4()),
                "tenant_id": tenant_id,
                "universe_id": universe_id,
                "reference_source": source,
                "added_count": int(added_count or 0),
                "removed_count": int(removed_count or 0),
                "added_symbols": json.dumps(added_symbols or []),
                "removed_symbols": json.dumps(removed_symbols or []),
            })

            self.db.commit()

        except Exception:
            self._rollback()
            raise

    def get_sync_history(self, tenant_id: str, universe_id: str, limit: int = 10) -> pd.DataFrame:
        try:
            rows = self.db.execute(text("""
                SELECT
                    created_at,
                    reference_source,
                    added_count,
                    removed_count,
                    added_symbols,
                    removed_symbols
                FROM universe_sync_history
                WHERE tenant_id = :tenant_id
                  AND universe_id = :universe_id
                ORDER BY created_at DESC
                LIMIT :limit
            """), {
                "tenant_id": tenant_id,
                "universe_id": universe_id,
                "limit": int(limit),
            }).fetchall()

            return pd.DataFrame(rows, columns=[
                "created_at",
                "reference_source",
                "added_count",
                "removed_count",
                "added_symbols",
                "removed_symbols",
            ])

        except Exception:
            self._rollback()
            return pd.DataFrame()
