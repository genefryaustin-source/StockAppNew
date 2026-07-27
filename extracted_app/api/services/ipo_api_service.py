"""
api/services/ipo_api_service.py

IPO API Service

Backs GET /api/v1/ipo/calendar and GET /api/v1/ipo/{id}.

list_calendar wraps modules.ipo.service.list_ipo_events, a real,
tenant-scoped, filterable function that already existed -- no new query
logic there. get_event is new: no single-event lookup existed before
this, only the list function.
"""

from __future__ import annotations

import logging
from typing import Any

from api.services._portfolio_symbol_returns import _safe_rollback

logger = logging.getLogger(__name__)


class IPOAPIService:
    """API service for the IPO calendar."""

    def __init__(self, db):
        self.db = db

    def list_calendar(
        self,
        *,
        tenant_id: str,
        status: str | None = None,
        search: str | None = None,
        limit: int = 500,
    ) -> dict[str, Any]:
        """
        IPO events for a tenant, optionally filtered by status
        (upcoming/priced/withdrawn) and/or free-text search across
        company name, symbol, sector, and industry. Returns an empty
        list (not an exception) on a database error.
        """

        _safe_rollback(self.db)

        try:
            from modules.ipo.service import list_ipo_events

            events = list_ipo_events(
                self.db, tenant_id, status=status, search=search, limit=limit,
            )

        except Exception:
            logger.exception("Failed to list IPO calendar | tenant_id=%s", tenant_id)
            _safe_rollback(self.db)
            return {"tenant_id": tenant_id, "event_count": 0, "events": []}

        return {
            "tenant_id": tenant_id,
            "event_count": len(events),
            "events": [self._serialize(e, include_raw=False) for e in events],
        }

    def get_event(
        self,
        *,
        tenant_id: str,
        event_id: str,
    ) -> dict[str, Any] | None:
        """
        Single IPO event by id, scoped to tenant_id. Returns None if
        not found, doesn't belong to tenant_id, or on a database error
        -- the router turns that into a 404.
        """

        _safe_rollback(self.db)

        try:
            from modules.ipo.models import IPOEvent

            record = (
                self.db.query(IPOEvent)
                .filter(
                    IPOEvent.id == event_id,
                    IPOEvent.tenant_id == tenant_id,
                )
                .one_or_none()
            )

        except Exception:
            logger.exception("Failed to fetch IPO event | event_id=%s", event_id)
            _safe_rollback(self.db)
            return None

        if record is None:
            return None

        return self._serialize(record, include_raw=True)

    @staticmethod
    def _serialize(record, *, include_raw: bool) -> dict[str, Any]:
        data = {
            "id": record.id,
            "symbol": record.symbol,
            "company_name": record.company_name,
            "exchange": record.exchange,
            "ipo_date": record.ipo_date.isoformat() if record.ipo_date else None,
            "status": record.status,
            "price": record.price,
            "price_low": record.price_low,
            "price_high": record.price_high,
            "shares": record.shares,
            "deal_size": record.deal_size,
            "market_cap": record.market_cap,
            "sector": record.sector,
            "industry": record.industry,
            "country": record.country,
            "underwriters": record.underwriters,
            "source": record.source,
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "updated_at": record.updated_at.isoformat() if record.updated_at else None,
        }

        # description/raw_payload can be large -- included only on the
        # single-event detail lookup, not on every row of the calendar
        # list.
        if include_raw:
            data["description"] = record.description
            data["raw_payload"] = record.raw_payload

        return data