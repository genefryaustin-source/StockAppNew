"""
api/services/alerts_api_service.py

Alerts API Service

Backs POST /api/v1/alerts, GET /api/v1/alerts, and
POST /api/v1/alerts/{id}/acknowledge.

Wraps modules.alerts.service:
    - AlertService.create_alert -- fixed here in this same effort; the
      previous version always failed silently (tried to self-import a
      nonexistent function, then fell through to an insert that passed
      two columns AlertEvent doesn't have and omitted two NOT NULL
      columns it does). Confirmed zero real callers existed before
      fixing it, so this was a clean rewrite, not a breaking change.
    - list_alerts / acknowledge_alert -- already real, tenant-scoped,
      working functions; this only adds rollback safety and JSON
      serialization around them, no new query logic.
"""

from __future__ import annotations

import logging
from typing import Any

from api.services._portfolio_symbol_returns import _safe_rollback

logger = logging.getLogger(__name__)


class AlertsAPIService:
    """API service for alert creation, listing, and acknowledgment."""

    def __init__(self, db):
        self.db = db

    # ---------------------------------------------------------
    # Create
    # ---------------------------------------------------------

    def create_alert(
        self,
        *,
        tenant_id: str,
        symbol: str,
        title: str,
        alert_type: str = "general",
        message: str = "",
    ) -> dict[str, Any] | None:
        """
        Create a single alert. Returns None (not an exception) on a
        database error -- the router turns that into a clear failure
        response rather than a raw 500.
        """

        _safe_rollback(self.db)

        from modules.alerts.service import AlertService

        record = AlertService(self.db).create_alert(
            tenant_id=tenant_id,
            symbol=symbol,
            title=title,
            alert_type=alert_type,
            message=message,
        )

        if record is None:
            return None

        return self._serialize(record)

    # ---------------------------------------------------------
    # List
    # ---------------------------------------------------------

    def list_alerts(
        self,
        *,
        tenant_id: str,
        symbol: str | None = None,
        only_unacknowledged: bool = False,
        limit: int = 200,
    ) -> dict[str, Any]:
        """
        Alerts for a tenant, optionally filtered by symbol and/or
        unacknowledged-only. Returns an empty list (not an exception)
        on a database error.
        """

        _safe_rollback(self.db)

        try:
            from modules.alerts.service import list_alerts

            records = list_alerts(
                self.db,
                tenant_id,
                symbol=symbol,
                only_unack=only_unacknowledged,
                limit=limit,
            )

        except Exception:
            logger.exception("Failed to list alerts | tenant_id=%s", tenant_id)
            _safe_rollback(self.db)
            return {"tenant_id": tenant_id, "alert_count": 0, "alerts": []}

        alerts = [self._serialize(r) for r in records]

        return {
            "tenant_id": tenant_id,
            "alert_count": len(alerts),
            "alerts": alerts,
        }

    # ---------------------------------------------------------
    # Acknowledge
    # ---------------------------------------------------------

    def acknowledge_alert(
        self,
        *,
        tenant_id: str,
        alert_id: str,
    ) -> bool:
        """
        Mark an alert acknowledged. Scoped to tenant_id so one tenant
        can't acknowledge another tenant's alert by guessing its id.
        Returns False (not an exception) if the alert doesn't exist,
        doesn't belong to tenant_id, or a database error occurred.
        """

        _safe_rollback(self.db)

        try:
            from modules.alerts.service import acknowledge_alert

            return bool(acknowledge_alert(self.db, tenant_id, alert_id))

        except Exception:
            logger.exception(
                "Failed to acknowledge alert | tenant_id=%s alert_id=%s",
                tenant_id,
                alert_id,
            )
            _safe_rollback(self.db)
            return False

    # ---------------------------------------------------------
    # Internal
    # ---------------------------------------------------------

    @staticmethod
    def _serialize(record) -> dict[str, Any]:
        return {
            "id": record.id,
            "symbol": record.symbol,
            "alert_type": record.alert_type,
            "title": record.title,
            "message": record.message,
            "last_price": record.last_price,
            "support": record.support,
            "resistance": record.resistance,
            "previous_rating": record.previous_rating,
            "new_rating": record.new_rating,
            "acknowledged": bool(record.acknowledged),
            "acknowledged_at": record.acknowledged_at.isoformat() if record.acknowledged_at else None,
            "created_at": record.created_at.isoformat() if record.created_at else None,
        }