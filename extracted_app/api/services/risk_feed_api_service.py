"""
api/services/risk_feed_api_service.py

Risk Feed API Service

Backs GET /api/v1/risk (tenant-wide, across every active portfolio --
for the portfolio-scoped version see
api.services.portfolio_health_api_service and
modules.portfolio.portfolio_risk_api_service).

Wraps modules.risk_layer.engine.compute_risk_snapshot with
portfolio_id=None. Verified safe to call this way: its internal
_portfolio_ids_for_scope helper filters by tenant_id when no
portfolio_id is given, unlike some of the recommendation engines (see
recommendations_feed_api_service.py for a case where that isn't true
and had to be worked around).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class RiskFeedAPIService:
    """API service for a tenant-wide risk snapshot across every active portfolio."""

    def __init__(self, db):
        self.db = db

    def get_risk(self, *, tenant_id: str) -> dict[str, Any]:

        try:
            from modules.risk_layer.engine import compute_risk_snapshot

            snapshot = compute_risk_snapshot(
                self.db,
                tenant_id=tenant_id,
                portfolio_id=None,
                include_scanner=False,
                include_valuation=False,
                include_external_providers=False,
            )
        except Exception:
            logger.exception("Tenant-wide risk snapshot failed | tenant_id=%s", tenant_id)
            try:
                self.db.rollback()
            except Exception:
                pass
            return {
                "tenant_id": tenant_id,
                "available": False,
                "reason": "Risk snapshot could not be computed.",
            }

        positions_df = snapshot.pop("positions", None)
        position_count = int(len(positions_df)) if positions_df is not None else 0

        snapshot = self._json_safe(snapshot)

        snapshot["tenant_id"] = tenant_id
        snapshot["available"] = True
        snapshot["position_count"] = position_count

        return snapshot

    @staticmethod
    def _json_safe(value: Any) -> Any:
        """
        compute_risk_snapshot's fields are a mix of plain dicts and at
        least one raw DataFrame (stress_test, from
        RiskAnalyticsService.stress_test()) -- unlike
        portfolio_health_api_service.py, which only ever returned a
        curated subset that happened to avoid that field, this returns
        the whole snapshot, so every field needs to survive JSON
        serialization.
        """
        import numpy as np
        import pandas as pd

        if isinstance(value, pd.DataFrame):
            if value.empty:
                return []
            clean = value.replace([np.inf, -np.inf], np.nan).where(
                pd.notnull(value), None
            )
            return clean.to_dict(orient="records")

        if isinstance(value, pd.Series):
            return RiskFeedAPIService._json_safe(value.to_dict())

        if isinstance(value, dict):
            return {k: RiskFeedAPIService._json_safe(v) for k, v in value.items()}

        if isinstance(value, (list, tuple)):
            return [RiskFeedAPIService._json_safe(v) for v in value]

        if isinstance(value, np.generic):
            return value.item()

        if isinstance(value, float) and not np.isfinite(value):
            return None

        return value