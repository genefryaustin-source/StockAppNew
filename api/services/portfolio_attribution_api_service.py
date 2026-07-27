from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from models.trading import Portfolio
from modules.trading_intelligence.trade_attribution_engine import (
    TradeAttributionEngine,
)

from api.services._portfolio_symbol_returns import _safe_rollback

logger = logging.getLogger(__name__)


class PortfolioAttributionAPIService:
    """
    API service for portfolio trade attribution.

    Responsibilities
    ----------------
    • Validate tenant ownership
    • Execute TradeAttributionEngine
    • Normalize pandas/DataFrames
    • Return JSON-safe payload

    All attribution calculations remain inside
    TradeAttributionEngine.
    """

    def __init__(self, db: Session):
        self.db = db

    # ==========================================================
    # Public API
    # ==========================================================

    def get_attribution(
        self,
        *,
        tenant_id: str,
        portfolio_id: str,
    ) -> dict[str, Any] | None:

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

        engine = TradeAttributionEngine(self.db)

        try:

            summary = engine.build_summary(portfolio_id)

            linkage = engine.load_attribution_table(
                portfolio_id
            )

            signal = engine.signal_attribution(
                portfolio_id
            )

            sector = engine.sector_attribution(
                portfolio_id
            )

            conviction = (
                engine.conviction_band_attribution(
                    portfolio_id
                )
            )

            exposure = (
                engine.open_recommendation_exposure(
                    portfolio_id
                )
            )

            return {

                "summary": self._build_summary(
                    portfolio=portfolio,
                    summary=summary,
                ),

                "trade_linkage":
                    self._normalize_dataframe(
                        linkage
                    ),

                "signal_attribution":
                    self._normalize_dataframe(
                        signal
                    ),

                "sector_attribution":
                    self._normalize_dataframe(
                        sector
                    ),

                "conviction_band_attribution":
                    self._normalize_dataframe(
                        conviction
                    ),

                "open_recommendation_exposure":
                    self._normalize_dataframe(
                        exposure
                    ),
            }

        except Exception:

            logger.exception(
                "Portfolio attribution failed."
            )

            _safe_rollback(self.db)

            raise

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
    # Summary
    # ==========================================================

    def _build_summary(
        self,
        *,
        portfolio,
        summary,
    ) -> dict[str, Any]:

        if hasattr(summary, "to_dict"):
            summary_dict = summary.to_dict()

        elif hasattr(summary, "__dict__"):
            summary_dict = asdict(summary)

        else:
            summary_dict = {}

        summary_dict.update({

            "portfolio_id": str(
                portfolio.id
            ),

            "portfolio_name": getattr(
                portfolio,
                "name",
                None,
            ),

        })

        return self._normalize_value(
            summary_dict
        )

    # ==========================================================
    # DataFrame Normalization
    # ==========================================================

    def _normalize_dataframe(
        self,
        df: pd.DataFrame | None,
    ) -> list[dict[str, Any]]:

        if df is None:
            return []

        if df.empty:
            return []

        df = df.astype(object)

        df = df.where(
            pd.notnull(df),
            None,
        )

        records = []

        for row in df.to_dict(
            orient="records"
        ):

            cleaned = {}

            for key, value in row.items():

                cleaned[key] = (
                    self._normalize_value(
                        value
                    )
                )

            records.append(cleaned)

        return records

    # ==========================================================
    # JSON Normalization
    # ==========================================================

    def _normalize_value(
        self,
        value,
    ):

        if isinstance(value, dict):

            return {
                k: self._normalize_value(v)
                for k, v in value.items()
            }

        if isinstance(value, list):

            return [
                self._normalize_value(v)
                for v in value
            ]

        if value is None:
            return None

        if value is pd.NaT:
            return None

        if isinstance(
            value,
            pd.Timestamp,
        ):
            return value.isoformat()

        if hasattr(
            value,
            "isoformat",
        ) and not isinstance(
            value,
            str,
        ):
            try:
                return value.isoformat()
            except Exception:
                pass

        if isinstance(
            value,
            np.integer,
        ):
            return int(value)

        if isinstance(
            value,
            np.floating,
        ):
            return float(value)

        if isinstance(
            value,
            np.bool_,
        ):
            return bool(value)

        if hasattr(
            value,
            "item",
        ):
            try:
                return value.item()
            except Exception:
                pass

        return value