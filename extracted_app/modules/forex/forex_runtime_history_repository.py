"""
===============================================================================
forex_runtime_history_repository.py
Sprint 30 - Phase 2 (Part 2)
Runtime History Repository
===============================================================================
"""

from __future__ import annotations

import json
import logging

from typing import Any, Dict, List, Optional

from sqlalchemy import text

from modules.forex.forex_runtime_history_models import (
    CurrencyStrengthHistory,
    ForexRuntimeSnapshot,
    ProviderRuntimeHistory,
    RegimeHistory,
    RuntimeAIHistory,
    RuntimePortfolioHistory,
    RuntimeRiskHistory,
    RuntimeTimeline,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Repository
# =============================================================================


class ForexRuntimeHistoryRepository:

    def __init__(self, db=None):

        self.db = db

    # -------------------------------------------------------------------------
    # helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _loads(payload):

        if payload is None:
            return {}

        if isinstance(payload, dict):
            return payload

        if isinstance(payload, str):
            try:
                return json.loads(payload)
            except Exception:
                return {}

        return {}

    # -------------------------------------------------------------------------
    # history
    # -------------------------------------------------------------------------

    def load_runtime_history(
        self,
        runtime_id: str,
    ) -> RuntimeTimeline:

        timeline = RuntimeTimeline()

        if self.db is None:
            return timeline

        rows = self.db.execute(
            text(
                """
                SELECT
                    *
                FROM forex_runtime_history
                WHERE runtime_id=:runtime_id
                ORDER BY created_at
                """
            ),
            {
                "runtime_id": runtime_id,
            },
        ).mappings()

        for row in rows:

            timeline.add(
                self._build_snapshot(row)
            )

        return timeline

    # -------------------------------------------------------------------------

    def load_latest_runtime(
        self,
        tenant_id: str,
        user_id: Optional[str] = None,
    ) -> Optional[ForexRuntimeSnapshot]:

        if self.db is None:
            return None

        sql = """
        SELECT *
        FROM forex_runtime_history
        WHERE tenant_id=:tenant_id
        """

        params = {
            "tenant_id": tenant_id,
        }

        if user_id:

            sql += """
            AND user_id=:user_id
            """

            params["user_id"] = user_id

        sql += """
        ORDER BY created_at DESC
        LIMIT 1
        """

        row = (
            self.db.execute(
                text(sql),
                params,
            )
            .mappings()
            .first()
        )

        if row is None:
            return None

        return self._build_snapshot(row)

    # -------------------------------------------------------------------------

    def load_history_for_portfolio(
        self,
        portfolio_id: str,
    ) -> RuntimeTimeline:

        timeline = RuntimeTimeline()

        if self.db is None:
            return timeline

        rows = self.db.execute(
            text(
                """
                SELECT *
                FROM forex_runtime_history
                WHERE portfolio_id=:portfolio_id
                ORDER BY created_at
                """
            ),
            {
                "portfolio_id": portfolio_id,
            },
        ).mappings()

        for row in rows:
            timeline.add(
                self._build_snapshot(row)
            )

        return timeline

    # -------------------------------------------------------------------------

    def load_history_for_user(
        self,
        tenant_id: str,
        user_id: str,
    ) -> RuntimeTimeline:

        timeline = RuntimeTimeline()

        if self.db is None:
            return timeline

        rows = self.db.execute(
            text(
                """
                SELECT *
                FROM forex_runtime_history
                WHERE
                    tenant_id=:tenant_id
                AND
                    user_id=:user_id
                ORDER BY created_at
                """
            ),
            {
                "tenant_id": tenant_id,
                "user_id": user_id,
            },
        ).mappings()

        for row in rows:

            timeline.add(
                self._build_snapshot(row)
            )

        return timeline

    # -------------------------------------------------------------------------
    # deserialize
    # -------------------------------------------------------------------------

    def _build_snapshot(
        self,
        row,
    ) -> ForexRuntimeSnapshot:

        payload = self._loads(
            row.get("payload")
        )

        provider_history = []

        for item in payload.get(
            "provider_history",
            [],
        ):

            provider_history.append(
                ProviderRuntimeHistory(
                    **item,
                )
            )

        strength = []

        for item in payload.get(
            "currency_strength",
            [],
        ):

            strength.append(
                CurrencyStrengthHistory(
                    **item,
                )
            )

        regimes = []

        for item in payload.get(
            "regime_history",
            [],
        ):

            regimes.append(
                RegimeHistory(
                    **item,
                )
            )

        ai_history = []

        for item in payload.get(
            "ai_history",
            [],
        ):

            ai_history.append(
                RuntimeAIHistory(
                    **item,
                )
            )

        risk = None

        if payload.get("risk_history"):

            risk = RuntimeRiskHistory(
                **payload["risk_history"]
            )

        portfolio = None

        if payload.get(
            "portfolio_history"
        ):

            portfolio = RuntimePortfolioHistory(
                **payload["portfolio_history"]
            )

        return ForexRuntimeSnapshot(

            runtime_id=row["runtime_id"],

            tenant_id=row["tenant_id"],

            user_id=row["user_id"],

            portfolio_id=row["portfolio_id"],

            build_number=row["build_number"],

            build_started_at=row["build_started_at"],

            build_completed_at=row["build_completed_at"],

            provider_history=provider_history,

            currency_strength=strength,

            regime_history=regimes,

            ai_history=ai_history,

            risk_history=risk,

            portfolio_history=portfolio,

            metadata=self._loads(
                row.get("metadata")
            ),
        )


# =============================================================================
# Singleton
# =============================================================================

_REPOSITORY = None


def get_forex_runtime_history_repository(
    db=None,
):

    global _REPOSITORY

    if (
        _REPOSITORY is None
        or getattr(_REPOSITORY, "db", None) is not db
    ):
        _REPOSITORY = ForexRuntimeHistoryRepository(
            db=db,
        )

    return _REPOSITORY