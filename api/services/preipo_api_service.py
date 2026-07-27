"""
api/services/preipo_api_service.py

Pre-IPO API Service

Backs GET /api/v1/preipo/companies.

Wraps modules.preipo.service.list_preipo_companies, a real,
tenant-scoped, filterable function that already existed -- no new query
logic here, just rollback safety and JSON serialization.
"""

from __future__ import annotations

import logging
from typing import Any

from api.services._portfolio_symbol_returns import _safe_rollback

logger = logging.getLogger(__name__)


class PreIPOAPIService:
    """API service for pre-IPO company tracking."""

    def __init__(self, db):
        self.db = db

    def list_companies(
        self,
        *,
        tenant_id: str,
        search: str | None = None,
        min_score: float | None = None,
        limit: int = 500,
    ) -> dict[str, Any]:
        """
        Pre-IPO companies for a tenant, optionally filtered by
        free-text search (company name, ticker hint, sector) and/or a
        minimum IPO probability score, sorted by that score descending.
        Returns an empty list (not an exception) on a database error.
        """

        _safe_rollback(self.db)

        try:
            from modules.preipo.service import list_preipo_companies

            companies = list_preipo_companies(
                self.db, tenant_id, search=search, min_score=min_score, limit=limit,
            )

        except Exception:
            logger.exception(
                "Failed to list pre-IPO companies | tenant_id=%s", tenant_id
            )
            _safe_rollback(self.db)
            return {"tenant_id": tenant_id, "company_count": 0, "companies": []}

        return {
            "tenant_id": tenant_id,
            "company_count": len(companies),
            "companies": [self._serialize(c) for c in companies],
        }

    @staticmethod
    def _serialize(record) -> dict[str, Any]:
        return {
            "id": record.id,
            "company_name": record.company_name,
            "ticker_hint": record.ticker_hint,
            "sector": record.sector,
            "industry": record.industry,
            "country": record.country,
            "website": record.website,
            "last_known_valuation": record.last_known_valuation,
            "last_funding_amount": record.last_funding_amount,
            "last_funding_date": record.last_funding_date.isoformat() if record.last_funding_date else None,
            "last_funding_round": record.last_funding_round,
            "lead_investors": record.lead_investors,
            "sec_filing_status": record.sec_filing_status,
            "latest_sec_filing_date": record.latest_sec_filing_date.isoformat() if record.latest_sec_filing_date else None,
            "latest_sec_filing_type": record.latest_sec_filing_type,
            "latest_sec_filing_url": record.latest_sec_filing_url,
            "ipo_probability_score": record.ipo_probability_score,
            "ipo_readiness_score": record.ipo_readiness_score,
            "expected_ipo_window": record.expected_ipo_window,
            "confidence": record.confidence,
            "source": record.source,
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "updated_at": record.updated_at.isoformat() if record.updated_at else None,
        }