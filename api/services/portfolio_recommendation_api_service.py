"""
api/services/portfolio_recommendation_api_service.py

Portfolio Recommendation API Service

Backs GET /api/v1/portfolio/{portfolio_id}/recommendations.

Wraps modules.trading_intelligence.recommendation_orchestrator.
RecommendationOrchestrator (generation) and
modules.trading_intelligence.recommendation_lifecycle_engine.
RecommendationLifecycleEngine (reading) -- all recommendation logic
stays there.

Responsibilities here:
    - Validate tenant ownership
    - Generate recommendations when none exist yet
    - Load and normalize recommendations for JSON
    - Return the API payload
"""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any

import numpy as np
import pandas as pd

from models.trading import Portfolio

from modules.trading_intelligence.recommendation_orchestrator import (
    RecommendationOrchestrator,
)
from modules.trading_intelligence.recommendation_lifecycle_engine import (
    RecommendationLifecycleEngine,
)

from api.services._portfolio_symbol_returns import _safe_rollback

logger = logging.getLogger(__name__)


class PortfolioRecommendationAPIService:
    """
    API service for portfolio trade recommendations. Business logic
    stays in RecommendationOrchestrator/RecommendationLifecycleEngine;
    this validates tenant ownership, triggers generation when nothing
    exists yet, and shapes the response.
    """

    def __init__(self, db):
        self.db = db

    # ==========================================================
    # Public API
    # ==========================================================

    def get_recommendations(
        self,
        *,
        tenant_id: str,
        portfolio_id: str,
        generate_if_missing: bool = True,
        top_n: int = 25,
    ) -> dict[str, Any] | None:
        """
        Existing recommendations for a portfolio, generating a fresh
        batch first if none exist yet and generate_if_missing is True.

        Returns None if the portfolio doesn't exist or doesn't belong
        to tenant_id -- the router turns that into a 404.
        """

        # This service's db session is cached and reused across every
        # request to this endpoint for the life of the process (see
        # ModuleRegistry._load). If an earlier request left it in a
        # failed-transaction state (Postgres) and didn't roll back,
        # every query below -- including this very first one -- would
        # otherwise fail immediately. Rolling back a clean session is a
        # harmless no-op.
        _safe_rollback(self.db)

        portfolio = self._validate_portfolio(
            tenant_id=tenant_id,
            portfolio_id=portfolio_id,
        )

        if portfolio is None:
            return None

        lifecycle = RecommendationLifecycleEngine(self.db)

        df = lifecycle.get_all_recommendations(portfolio_id=portfolio_id)

        if df.empty and generate_if_missing:
            self._generate_recommendations(
                tenant_id=tenant_id,
                portfolio_id=portfolio_id,
                top_n=top_n,
            )
            df = lifecycle.get_all_recommendations(portfolio_id=portfolio_id)

        recommendations = self._dataframe_to_records(df)

        return {
            "summary": self._build_summary(
                portfolio=portfolio,
                recommendations=recommendations,
            ),
            "recommendations": recommendations,
        }

    # ==========================================================
    # Normalization
    # ==========================================================

    def _dataframe_to_records(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        if df is None or df.empty:
            return []

        # Object dtype so None survives; NaN/NaT -> None; every value
        # normalized to a native, JSON-safe Python type.
        clean = df.astype(object)
        clean = clean.where(pd.notnull(clean), None)

        for column in clean.columns:
            clean[column] = clean[column].apply(self._normalize_value)

        return clean.to_dict("records")

    def _normalize_value(self, value):

        if value is None or value is pd.NaT:
            return None

        if isinstance(value, pd.Timestamp):
            return value.isoformat()

        if isinstance(value, datetime):
            return value.isoformat()

        if isinstance(value, Decimal):
            return float(value)

        if isinstance(value, np.integer):
            return int(value)

        if isinstance(value, np.floating):
            return float(value)

        if isinstance(value, np.bool_):
            return bool(value)

        if hasattr(value, "item"):
            try:
                return value.item()
            except Exception:
                pass

        return value

    # ==========================================================
    # Portfolio Validation
    # ==========================================================

    def _validate_portfolio(
        self,
        *,
        tenant_id: str,
        portfolio_id: str,
    ):
        return (
            self.db.query(Portfolio)
            .filter(
                Portfolio.id == portfolio_id,
                Portfolio.tenant_id == tenant_id,
            )
            .one_or_none()
        )

    # ==========================================================
    # Recommendation Generation
    # ==========================================================

    def _generate_recommendations(
        self,
        *,
        tenant_id: str,
        portfolio_id: str,
        top_n: int,
    ) -> None:

        try:
            engine = RecommendationOrchestrator(
                db=self.db,
                tenant_id=tenant_id,
                portfolio_id=portfolio_id,
            )

            engine.ensure_schema()

            recommendations = engine.generate_recommendations(top_n=top_n)

            if recommendations:
                engine.save_recommendations(recommendations)

        except Exception:
            logger.exception("Unable to generate recommendations.")
            _safe_rollback(self.db)

    # ==========================================================
    # Summary
    # ==========================================================

    def _build_summary(
        self,
        *,
        portfolio,
        recommendations: list[dict[str, Any]],
    ) -> dict[str, Any]:

        actions: dict[str, int] = {}
        total_confidence = 0.0

        for rec in recommendations:
            action = str(rec.get("recommendation", "UNKNOWN")).upper()
            actions[action] = actions.get(action, 0) + 1
            total_confidence += float(rec.get("confidence_score", 0) or 0)

        average_confidence = (
            round(total_confidence / len(recommendations), 2)
            if recommendations
            else 0.0
        )

        return {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "portfolio_id": str(portfolio.id),
            "portfolio_name": getattr(portfolio, "name", None),
            "recommendation_count": len(recommendations),
            "average_confidence": average_confidence,
            "action_breakdown": actions,
        }