from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from models.trading import Portfolio, PortfolioPosition
from modules.market_data.service import get_price_history
from modules.portfolio.risk_analytics_service import RiskAnalyticsService


logger = logging.getLogger(__name__)


class PortfolioRiskAPIService:
    """
    API orchestration service for portfolio risk analytics.
    """

    def __init__(self, db: Any):
        self.db = db

    def get_portfolio_risk(
        self,
        *,
        tenant_id: str,
        portfolio_id: str,
    ) -> dict[str, Any] | None:

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

        positions = (
            self.db.query(PortfolioPosition)
            .filter(
                PortfolioPosition.portfolio_id == portfolio_id,
            )
            .all()
        )

        position_rows: list[dict[str, Any]] = []
        return_series: list[pd.Series] = []
        history_failures: list[dict[str, str]] = []

        for position in positions:
            symbol = str(
                getattr(position, "symbol", "") or ""
            ).strip().upper()

            if not symbol:
                continue

            position_rows.append(
                {
                    "Symbol": symbol,
                    "Market Value": self._to_float(
                        getattr(position, "market_value", 0.0)
                    ),
                    "Unrealized P&L": self._to_float(
                        getattr(position, "unrealized_pnl", 0.0)
                    ),
                    "Realized P&L": self._to_float(
                        getattr(position, "realized_pnl", 0.0)
                    ),
                }
            )

            try:
                history = get_price_history(
                    self.db,
                    symbol,
                    period="1y",
                    interval="1d",
                )
            except Exception as exc:
                logger.exception(
                    "Failed to load price history for portfolio risk: "
                    "portfolio_id=%s symbol=%s",
                    portfolio_id,
                    symbol,
                )
                history_failures.append(
                    {
                        "symbol": symbol,
                        "reason": str(exc),
                    }
                )
                continue

            if history is None or history.empty:
                history_failures.append(
                    {
                        "symbol": symbol,
                        "reason": "No historical price data available.",
                    }
                )
                continue

            close_series = self._extract_close_series(history)

            if close_series is None or close_series.empty:
                history_failures.append(
                    {
                        "symbol": symbol,
                        "reason": (
                            "Historical data does not contain usable close prices."
                        ),
                    }
                )
                continue

            symbol_returns = (
                close_series
                .pct_change()
                .replace([np.inf, -np.inf], np.nan)
                .dropna()
            )

            if symbol_returns.empty:
                history_failures.append(
                    {
                        "symbol": symbol,
                        "reason": (
                            "Historical data did not produce usable returns."
                        ),
                    }
                )
                continue

            symbol_returns.name = symbol
            return_series.append(symbol_returns)

        positions_df = pd.DataFrame(
            position_rows,
            columns=[
                "Symbol",
                "Market Value",
                "Unrealized P&L",
                "Realized P&L",
            ],
        )

        returns_df = self._build_returns_dataframe(return_series)

        analytics = RiskAnalyticsService(
            returns_df=returns_df,
            positions_df=positions_df,
        )

        stress_result = analytics.stress_test()
        contribution_result = analytics.position_risk_contribution()

        report = {
            "summary": {
                "portfolio_id": str(portfolio_id),
                "portfolio_name": getattr(portfolio, "name", None),
                "positions": len(position_rows),
                "symbols_with_history": len(return_series),
                "portfolio_value": round(
                    self._dataframe_sum(
                        positions_df,
                        "Market Value",
                    ),
                    2,
                ),
                "unrealized_pnl": round(
                    self._dataframe_sum(
                        positions_df,
                        "Unrealized P&L",
                    ),
                    2,
                ),
                "realized_pnl": round(
                    self._dataframe_sum(
                        positions_df,
                        "Realized P&L",
                    ),
                    2,
                ),
            },
            "value_at_risk": {
                "historical": analytics.historical_var(),
                "parametric": analytics.parametric_var(),
                "expected_shortfall": analytics.expected_shortfall(),
            },
            "concentration": analytics.concentration_risk(),
            "volatility": analytics.volatility_regime(),
            "drawdown": analytics.drawdown_alert(),
            "stress_testing": self._records(stress_result),
            "risk_contribution": self._records(contribution_result),
            "advanced_models": analytics.advanced_risk_cross_check(),
            "data_quality": {
                "requested_symbols": len(position_rows),
                "symbols_with_history": len(return_series),
                "symbols_without_history": len(history_failures),
                "history_failures": history_failures,
            },
        }

        return self._json_safe(report)

    @staticmethod
    def _extract_close_series(
        history: pd.DataFrame,
    ) -> pd.Series | None:

        column_map = {
            str(column).strip().lower().replace("_", " "): column
            for column in history.columns
        }

        close_column = None

        for candidate in (
            "close",
            "adj close",
            "adjusted close",
            "adjclose",
        ):
            if candidate in column_map:
                close_column = column_map[candidate]
                break

        if close_column is None:
            return None

        close_series = (
            pd.to_numeric(
                history[close_column],
                errors="coerce",
            )
            .replace([np.inf, -np.inf], np.nan)
            .dropna()
        )

        if close_series.empty:
            return None

        return close_series.sort_index()

    @staticmethod
    def _build_returns_dataframe(
        return_series: list[pd.Series],
    ) -> pd.DataFrame:

        if not return_series:
            return pd.DataFrame()

        returns_df = pd.concat(
            return_series,
            axis=1,
            join="inner",
        )

        return (
            returns_df
            .replace([np.inf, -np.inf], np.nan)
            .dropna(how="all")
        )

    @staticmethod
    def _records(value: Any) -> list[dict[str, Any]]:

        if value is None:
            return []

        if isinstance(value, pd.DataFrame):
            if value.empty:
                return []

            clean = (
                value
                .replace([np.inf, -np.inf], np.nan)
                .where(pd.notnull(value), None)
            )

            return clean.to_dict(orient="records")

        if isinstance(value, pd.Series):
            if value.empty:
                return []

            return [
                {
                    str(key): PortfolioRiskAPIService._json_safe(item)
                    for key, item in value.to_dict().items()
                }
            ]

        if isinstance(value, list):
            return [
                PortfolioRiskAPIService._json_safe(item)
                for item in value
            ]

        if isinstance(value, dict):
            return [
                PortfolioRiskAPIService._json_safe(value)
            ]

        return [
            {
                "value": PortfolioRiskAPIService._json_safe(value),
            }
        ]

    @staticmethod
    def _dataframe_sum(
        frame: pd.DataFrame,
        column: str,
    ) -> float:

        if frame.empty or column not in frame.columns:
            return 0.0

        values = pd.to_numeric(
            frame[column],
            errors="coerce",
        )

        return float(values.fillna(0.0).sum())

    @staticmethod
    def _to_float(value: Any) -> float:

        try:
            if value is None or pd.isna(value):
                return 0.0

            return float(value)

        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _json_safe(value: Any) -> Any:

        if value is None:
            return None

        if isinstance(value, dict):
            return {
                str(key): PortfolioRiskAPIService._json_safe(item)
                for key, item in value.items()
            }

        if isinstance(value, (list, tuple, set)):
            return [
                PortfolioRiskAPIService._json_safe(item)
                for item in value
            ]

        if isinstance(value, pd.DataFrame):
            return PortfolioRiskAPIService._records(value)

        if isinstance(value, pd.Series):
            return {
                str(key): PortfolioRiskAPIService._json_safe(item)
                for key, item in value.to_dict().items()
            }

        if isinstance(value, (pd.Timestamp, pd.Timedelta)):
            return str(value)

        if isinstance(value, np.generic):
            value = value.item()

        if isinstance(value, float):
            if not np.isfinite(value):
                return None

            return value

        try:
            if pd.isna(value):
                return None
        except (TypeError, ValueError):
            pass

        return value
