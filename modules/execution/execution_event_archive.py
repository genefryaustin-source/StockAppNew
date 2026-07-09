"""
execution_event_archive.py

Sprint 39.4

Institutional Execution Event Archive

Archives immutable execution events while preserving complete
replay capability.

Execution Events
        ↓
ExecutionEventArchive
        ↓
Archive
        ↓
Restore
        ↓
Replay

The archive layer NEVER modifies event contents.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from .execution_event_replayer import (
    ExecutionEventReplayer,
    get_execution_event_replayer,
)


# ==============================================================================
# Helpers
# ==============================================================================

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ==============================================================================
# Archive Engine
# ==============================================================================


class ExecutionEventArchive:

    def __init__(
        self,
        *,
        db,
        replayer: Optional[
            ExecutionEventReplayer
        ] = None,
    ):

        self.db = db

        self.replayer = (
            replayer
            or get_execution_event_replayer(
                db=db,
            )
        )

        self.ensure_tables()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def ensure_tables(self):

        if self.db is None:
            return

        self.db.execute(text("""
        CREATE TABLE IF NOT EXISTS execution_event_archive (

            archive_id VARCHAR(64) PRIMARY KEY,

            entity_type VARCHAR(50),

            entity_id VARCHAR(100),

            created_at TIMESTAMP,

            event_count INTEGER,

            checksum VARCHAR(128),

            compressed BOOLEAN,

            archive_data BYTEA

        )
        """))

        self.db.commit()

    # ==============================================================
    # Public API
    # ==============================================================

    def archive_execution(
        self,
        execution_id: str,
    ):

        events = self.replayer.load_events(
            execution_id=execution_id,
        )

        return self._archive(

            entity_type="execution",

            entity_id=execution_id,

            events=events,

        )

    # --------------------------------------------------------------

    def archive_order(
        self,
        broker_order_id: str,
    ):

        events = self.replayer.load_events(
            broker_order_id=broker_order_id,
        )

        return self._archive(

            entity_type="order",

            entity_id=broker_order_id,

            events=events,

        )

    # --------------------------------------------------------------

    def archive_position(
        self,
        position_id: str,
    ):

        events = self.replayer.load_events(
            position_id=position_id,
        )

        return self._archive(

            entity_type="position",

            entity_id=position_id,

            events=events,

        )

    # --------------------------------------------------------------

    def archive_account(
        self,
        account_id: str,
    ):

        events = self.replayer.load_events(
            account_id=account_id,
        )

        return self._archive(

            entity_type="account",

            entity_id=account_id,

            events=events,

        )

    # --------------------------------------------------------------

    def archive_portfolio(
        self,
        portfolio_id: str,
    ):

        events = self.replayer.load_events(
            portfolio_id=portfolio_id,
        )

        return self._archive(

            entity_type="portfolio",

            entity_id=portfolio_id,

            events=events,

        )

    # --------------------------------------------------------------

    def archive_before(
        self,
        timestamp: datetime,
    ):

        events = self.replayer.load_events()

        filtered = []

        for event in events:

            ts = (
                event.get("occurred_at")
                or event.get("created_at")
            )

            if ts is None:
                continue

            if isinstance(ts, str):

                ts = datetime.fromisoformat(
                    ts
                )

            if ts < timestamp:

                filtered.append(
                    event
                )

        return self._archive(

            entity_type="historical",

            entity_id=timestamp.isoformat(),

            events=filtered,

        )

    # ==============================================================
    # Restore
    # ==============================================================

    def restore(
        self,
        archive_id: str,
    ) -> List[Dict]:

        row = self.db.execute(text("""
        SELECT archive_data
        FROM execution_event_archive
        WHERE archive_id=:id
        """), {

            "id": archive_id,

        }).mappings().first()

        if row is None:

            return []

        data = gzip.decompress(
            row["archive_data"]
        )

        return json.loads(
            data.decode()
        )

    # ==============================================================
    # Verify
    # ==============================================================

    def verify_archive(
        self,
        archive_id: str,
    ) -> Dict[str, Any]:

        events = self.restore(
            archive_id
        )

        checksum = self._checksum(
            events
        )

        row = self.db.execute(text("""
        SELECT *

        FROM execution_event_archive

        WHERE archive_id=:id
        """), {

            "id": archive_id,

        }).mappings().first()

        if row is None:

            return {

                "valid": False,

                "reason": "Archive missing",

            }

        return {

            "valid": (
                checksum
                == row["checksum"]
            ),

            "checksum": checksum,

            "expected": row["checksum"],

            "event_count": len(events),

        }

    # ==============================================================
    # Purge
    # ==============================================================

    def purge_archive(
        self,
        archive_id: str,
    ):

        self.db.execute(text("""
        DELETE
        FROM execution_event_archive
        WHERE archive_id=:id
        """), {

            "id": archive_id,

        })

        self.db.commit()

    # ==============================================================
    # Statistics
    # ==============================================================

    def statistics(
        self,
    ) -> Dict[str, Any]:

        row = self.db.execute(text("""
        SELECT

            COUNT(*) archives,

            COALESCE(SUM(event_count),0)
                events,

            COALESCE(
                SUM(
                    OCTET_LENGTH(
                        archive_data
                    )
                ),
                0
            )
                bytes,

            MIN(created_at)
                oldest,

            MAX(created_at)
                newest

        FROM execution_event_archive
        """)).mappings().first()

        return {

            "archives":
                row["archives"],

            "events_archived":
                row["events"],

            "storage_bytes":
                row["bytes"],

            "oldest_archive":
                row["oldest"],

            "newest_archive":
                row["newest"],

        }

    # ==============================================================
    # Internal
    # ==============================================================

    def _archive(

        self,

        *,

        entity_type,

        entity_id,

        events,

    ) -> Dict[str, Any]:

        archive_id = str(
            uuid.uuid4()
        )

        payload = json.dumps(
            events,
            default=str,
        ).encode()

        compressed = gzip.compress(
            payload
        )

        checksum = self._checksum(
            events
        )

        self.db.execute(text("""
        INSERT INTO execution_event_archive (

            archive_id,

            entity_type,

            entity_id,

            created_at,

            event_count,

            checksum,

            compressed,

            archive_data

        )

        VALUES (

            :archive_id,

            :entity_type,

            :entity_id,

            :created_at,

            :event_count,

            :checksum,

            TRUE,

            :archive_data

        )
        """), {

            "archive_id":
                archive_id,

            "entity_type":
                entity_type,

            "entity_id":
                entity_id,

            "created_at":
                utc_now().replace(
                    tzinfo=None,
                ),

            "event_count":
                len(events),

            "checksum":
                checksum,

            "archive_data":
                compressed,

        })

        self.db.commit()

        return {

            "archive_id":
                archive_id,

            "entity_type":
                entity_type,

            "entity_id":
                entity_id,

            "event_count":
                len(events),

            "checksum":
                checksum,

            "compressed":
                True,

        }

    # --------------------------------------------------------------

    def _checksum(
        self,
        events,
    ):

        encoded = json.dumps(

            events,

            sort_keys=True,

            default=str,

        ).encode()

        return hashlib.sha256(
            encoded
        ).hexdigest()


# ==============================================================================
# Factory
# ==============================================================================

_ARCHIVE = None


def get_execution_event_archive(
    *,
    db,
    cache: bool = True,
) -> ExecutionEventArchive:

    global _ARCHIVE

    if (
        not cache
        or _ARCHIVE is None
    ):

        _ARCHIVE = (
            ExecutionEventArchive(
                db=db,
            )
        )

    return _ARCHIVE