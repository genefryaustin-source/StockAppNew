from __future__ import annotations

import pandas as pd

from sqlalchemy import text

from modules.universe.symbol_validator import (
    normalize_symbol,
    validate_symbol,
)


class UniverseCleanupService:

    def __init__(self, db):

        self.db = db

        self._ensure_tables()

    # -------------------------------------------------
    # TABLES
    # -------------------------------------------------
    def _ensure_tables(self):

        self.db.execute(text("""
            CREATE TABLE IF NOT EXISTS symbol_blacklist (
                symbol TEXT PRIMARY KEY,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

        self.db.commit()

    # -------------------------------------------------
    # UNIVERSES
    # -------------------------------------------------
    def get_universes(self):

        rows = self.db.execute(text("""
            SELECT
                id,
                name
            FROM universes
            ORDER BY name
        """)).fetchall()

        return pd.DataFrame(rows, columns=[
            "id",
            "name",
        ])

    # -------------------------------------------------
    # SYMBOLS
    # -------------------------------------------------
    def get_universe_symbols(self, universe_id: str):

        rows = self.db.execute(text("""
            SELECT
                symbol
            FROM universe_symbols
            WHERE universe_id = :uid
            ORDER BY symbol
        """), {
            "uid": universe_id,
        }).fetchall()

        return pd.DataFrame(rows, columns=["symbol"])

    # -------------------------------------------------
    # DELETE SYMBOL
    # -------------------------------------------------
    def delete_symbol(
            self,
            universe_id: str,
            symbol: str,
            purge_snapshots: bool = True,
            blacklist: bool = False,
            reason: str = "Manual cleanup",
    ):

        sym = normalize_symbol(symbol)

        self.db.execute(text("""
            DELETE FROM universe_symbols
            WHERE universe_id = :uid
              AND UPPER(symbol) = :sym
        """), {
            "uid": universe_id,
            "sym": sym,
        })

        deleted_snapshots = 0

        if purge_snapshots:

            deleted_snapshots = self.db.execute(text("""
                DELETE FROM analytics_snapshots
                WHERE UPPER(symbol) = :sym
            """), {
                "sym": sym,
            }).rowcount

        if blacklist:

            self.db.execute(text("""
                INSERT OR IGNORE INTO symbol_blacklist (
                    symbol,
                    reason
                )
                VALUES (
                    :sym,
                    :reason
                )
            """), {
                "sym": sym,
                "reason": reason,
            })

        self.db.commit()

        return {
            "symbol": sym,
            "deleted_snapshots": deleted_snapshots,
        }

    # -------------------------------------------------
    # BLACKLIST
    # -------------------------------------------------
    def get_blacklist(self):

        rows = self.db.execute(text("""
            SELECT
                symbol,
                reason,
                created_at
            FROM symbol_blacklist
            ORDER BY created_at DESC
        """)).fetchall()

        return pd.DataFrame(rows, columns=[
            "symbol",
            "reason",
            "created_at",
        ])

    def is_blacklisted(self, symbol: str):

        sym = normalize_symbol(symbol)

        row = self.db.execute(text("""
            SELECT 1
            FROM symbol_blacklist
            WHERE symbol = :sym
        """), {
            "sym": sym,
        }).fetchone()

        return row is not None

    # -------------------------------------------------
    # AUTO CLEANUP PREVIEW
    # -------------------------------------------------
    def preview_suspicious_symbols(self, universe_id: str):

        symbols_df = self.get_universe_symbols(universe_id)

        if symbols_df.empty:
            return pd.DataFrame()

        rows = []

        for symbol in symbols_df["symbol"].tolist():

            valid, reason = validate_symbol(symbol)

            if not valid:

                rows.append({
                    "symbol": symbol,
                    "reason": reason,
                })

        return pd.DataFrame(rows)

    # -------------------------------------------------
    # AUTO CLEANUP EXECUTION
    # -------------------------------------------------
    def auto_cleanup_universe(
            self,
            universe_id: str,
            purge_snapshots: bool = True,
            blacklist: bool = True,
    ):

        suspicious = self.preview_suspicious_symbols(universe_id)

        if suspicious.empty:
            return {
                "removed": 0,
                "symbols": [],
            }

        removed = []

        for _, row in suspicious.iterrows():

            symbol = row["symbol"]
            reason = row["reason"]

            self.delete_symbol(
                universe_id=universe_id,
                symbol=symbol,
                purge_snapshots=purge_snapshots,
                blacklist=blacklist,
                reason=reason,
            )

            removed.append(symbol)

        return {
            "removed": len(removed),
            "symbols": removed,
        }