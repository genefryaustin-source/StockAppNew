"""
api/services/portfolio_health_api_service.py

Portfolio Health API Service

Backs GET /api/v1/portfolio/{portfolio_id}/health.

A fast, curated "traffic light" status check -- deliberately lighter
than /risk's full deep-dive report. Built on
modules.risk_layer.engine.compute_risk_snapshot, the same cross-asset
risk engine used across stocks/forex/options, called with the heavier
optional sub-analyses turned off for speed.
"""

from __future__ import annotations

import logging
from typing import Any

from models.trading import Portfolio

from api.services._portfolio_symbol_returns import _safe_rollback

logger = logging.getLogger(__name__)


class PortfolioHealthAPIService:
    """
    API service for a fast portfolio health check: overall status,
    active limit breaches, and headline risk numbers. Deliberately
    lighter than /risk (which returns the full deep-dive analytics
    report) -- this is meant to answer "is this portfolio OK" quickly,
    not replace the detailed report.

    Built on modules.risk_layer.engine.compute_risk_snapshot, the same
    cross-asset risk engine already used across stocks/forex/options,
    called with the heavier optional sub-analyses (scanner, valuation,
    external risk providers) turned off for speed -- flags
    compute_risk_snapshot already exposes for exactly this kind of lean
    call.
    """

    def __init__(self, db):
        self.db = db

    def get_health(
        self,
        *,
        tenant_id: str,
        portfolio_id: str,
    ) -> dict[str, Any] | None:
        """
        Overall status (healthy / warning / critical), active limit
        breaches, and headline risk numbers (equity, gross exposure,
        1-day 95% VaR, drawdown, concentration, market regime).

        status is "critical" if any limit is breached, "warning" if in
        a drawdown alert or over 30% concentrated in one name, else
        "healthy". Falls back to status="unknown" (not an exception) if
        the underlying risk snapshot itself fails. Returns None if the
        portfolio doesn't exist or doesn't belong to tenant_id -- the
        router turns that into a 404.
        """

        # See portfolio_correlation_api_service.py for why this matters:
        # this service's session is cached and reused for the life of
        # the process, so a prior request's unrolled-back failure would
        # otherwise break every query below, including this first one.
        _safe_rollback(self.db)

        portfolio = (
            self.db.query(Portfolio)
            .filter(
                Portfolio.id == portfolio_id,
                Portfolio.tenant_id == tenant_id,
            )
            .one_or_none()
        )

        if portfolio is None:
            return None

        from modules.risk_layer.engine import compute_risk_snapshot

        try:
            snapshot = compute_risk_snapshot(
                self.db,
                tenant_id=tenant_id,
                portfolio_id=portfolio_id,
                include_scanner=False,
                include_valuation=False,
                include_external_providers=False,
            )
        except Exception:
            logger.exception(
                "Risk snapshot failed for health check | %s", portfolio_id
            )
            _safe_rollback(self.db)
            return {
                "portfolio_id": str(portfolio_id),
                "status": "unknown",
                "reason": "Health check could not be computed.",
                "breaches": [],
            }

        breaches = snapshot.get("breaches") or []
        drawdown = snapshot.get("drawdown") or {}
        concentration = snapshot.get("concentration") or {}

        is_in_drawdown_alert = bool(drawdown.get("alert"))

        if breaches:
            status = "critical"
        elif is_in_drawdown_alert or concentration.get("max_weight", 0) > 0.30:
            status = "warning"
        else:
            status = "healthy"

        return {
            "portfolio_id": str(portfolio_id),
            "status": status,
            "equity": round(float(snapshot.get("equity") or 0.0), 2),
            "gross_exposure": round(float(snapshot.get("gross_exposure") or 0.0), 2),
            "var_95_1d": round(float(snapshot.get("var_95_1d") or 0.0), 2),
            "drawdown": drawdown,
            "concentration": concentration,
            "breaches": breaches,
            "market_regime": (snapshot.get("market_regime") or {}).get("label"),
        }