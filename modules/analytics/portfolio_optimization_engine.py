"""
modules/analytics/portfolio_optimization_engine.py

Portfolio Optimization Engine

Business-layer orchestration for portfolio optimization.

Responsibilities
----------------
- Validate the requested portfolio and optimization method.
- Load portfolio holdings from the existing portfolio tables.
- Load historical market data through modules.market_data.service.
- Build an overlapping daily-return matrix.
- Invoke the existing portfolio_optimizer algorithms.
- Return a FastAPI- and Streamlit-friendly result.

This module contains no Streamlit or FastAPI orchestration.
"""

from __future__ import annotations

import logging
import math
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from modules.analytics.portfolio_optimizer import (
    _build_return_matrix,
    optimize_max_sharpe,
    optimize_min_volatility,
    optimize_risk_parity,
)
from modules.market_data.service import get_price_history

from modules.portfolio.portfolio_service import (
    get_portfolio_service,
)

logger = logging.getLogger(__name__)


# ============================================================
# Configuration
# ============================================================

DEFAULT_LOOKBACK_DAYS = 252
MIN_LOOKBACK_DAYS = 30
MAX_LOOKBACK_DAYS = 3650
MIN_HISTORY_ROWS = 30

METHOD_MAX_SHARPE = "max_sharpe"
METHOD_MIN_VOLATILITY = "min_volatility"
METHOD_RISK_PARITY = "risk_parity"

SUPPORTED_METHODS = {
    METHOD_MAX_SHARPE,
    METHOD_MIN_VOLATILITY,
    METHOD_RISK_PARITY,
}

_METHOD_ALIASES = {
    "max sharpe": METHOD_MAX_SHARPE,
    "maximum sharpe": METHOD_MAX_SHARPE,
    "maximum_sharpe": METHOD_MAX_SHARPE,
    "max-sharpe": METHOD_MAX_SHARPE,
    "min volatility": METHOD_MIN_VOLATILITY,
    "minimum volatility": METHOD_MIN_VOLATILITY,
    "minimum_volatility": METHOD_MIN_VOLATILITY,
    "min-volatility": METHOD_MIN_VOLATILITY,
    "risk parity": METHOD_RISK_PARITY,
    "risk-parity": METHOD_RISK_PARITY,
}


# ============================================================
# Result Model
# ============================================================

@dataclass
class OptimizationResult:
    """Structured result returned by :class:`PortfolioOptimizationEngine`."""

    success: bool
    portfolio_id: Optional[str] = None
    portfolio_name: Optional[str] = None
    method: str = METHOD_MAX_SHARPE
    generated_at: str = ""
    holdings: int = 0
    symbols: int = 0
    lookback_days: int = DEFAULT_LOOKBACK_DAYS
    optimization: Optional[Dict[str, Any]] = None
    frontier: Optional[pd.DataFrame] = None
    message: str = ""

    def to_dict(self, *, include_frontier: bool = True) -> Dict[str, Any]:
        """
        Return a JSON-safe representation.

        The DataFrame frontier is converted to records when requested. This
        allows FastAPI serializers to consume the result without special
        pandas handling while preserving the DataFrame on the dataclass for
        existing Streamlit consumers.
        """
        payload = asdict(self)

        if include_frontier:
            payload["frontier"] = _dataframe_records(self.frontier)
        else:
            payload.pop("frontier", None)

        return _json_safe(payload)


# ============================================================
# Engine
# ============================================================

class PortfolioOptimizationEngine:
    """
    Reusable portfolio optimization application service.

    Parameters
    ----------
    db:
        Active SQLAlchemy session. Transaction ownership remains with the
        caller; this engine performs read-only operations.
    """

    def __init__(self, db: Session):
        if db is None:
            raise ValueError("A SQLAlchemy database session is required.")

        self.db = db

        self.portfolio_service = (
            get_portfolio_service(db)
        )

    # ========================================================
    # Public API
    # ========================================================

    def optimize(
        self,
        *,
        portfolio_id: str,
        method: str = METHOD_MAX_SHARPE,
        lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    ) -> OptimizationResult:
        """Optimize one portfolio and return a structured result."""
        generated_at = _utc_now_iso()

        try:
            clean_portfolio_id = self._validate_portfolio_id(portfolio_id)
            clean_method = self._normalize_method(method)
            clean_lookback = self._normalize_lookback_days(lookback_days)
        except ValueError as exc:
            return OptimizationResult(
                success=False,
                portfolio_id=str(portfolio_id or "") or None,
                method=self._normalize_method_soft(method),
                generated_at=generated_at,
                lookback_days=_safe_int(
                    lookback_days,
                    default=DEFAULT_LOOKBACK_DAYS,
                ),
                message=str(exc),
            )

        try:
            portfolio = self._load_portfolio(clean_portfolio_id)
        except Exception:
            logger.exception(
                "Unable to load portfolio %s.",
                clean_portfolio_id,
            )
            return self._failure(
                portfolio_id=clean_portfolio_id,
                method=clean_method,
                lookback_days=clean_lookback,
                generated_at=generated_at,
                message="Unable to load portfolio.",
            )

        if portfolio is None:
            return self._failure(
                portfolio_id=clean_portfolio_id,
                method=clean_method,
                lookback_days=clean_lookback,
                generated_at=generated_at,
                message="Portfolio not found.",
            )

        portfolio_name = _clean_optional_text(portfolio.get("name"))

        holdings = self._load_holdings(clean_portfolio_id)
        if holdings.empty:
            return self._failure(
                portfolio_id=clean_portfolio_id,
                portfolio_name=portfolio_name,
                method=clean_method,
                lookback_days=clean_lookback,
                generated_at=generated_at,
                message="Portfolio has no open long holdings.",
            )

        symbols = self._extract_symbols(holdings)
        if len(symbols) < 2:
            return self._failure(
                portfolio_id=clean_portfolio_id,
                portfolio_name=portfolio_name,
                method=clean_method,
                holdings=len(holdings),
                symbols=len(symbols),
                lookback_days=clean_lookback,
                generated_at=generated_at,
                message=(
                    "Portfolio must contain at least two valid symbols "
                    "for optimization."
                ),
            )

        logger.info(
            "Portfolio optimization started: portfolio=%s holdings=%s "
            "symbols=%s method=%s lookback_days=%s",
            clean_portfolio_id,
            len(holdings),
            len(symbols),
            clean_method,
            clean_lookback,
        )

        price_cache = self._load_price_history(
            symbols=symbols,
            lookback_days=clean_lookback,
        )

        history_stats = self._history_statistics(
            requested_symbols=symbols,
            price_cache=price_cache,
        )

        if int(history_stats["usable_symbols"]) < 2:
            return self._failure(
                portfolio_id=clean_portfolio_id,
                portfolio_name=portfolio_name,
                method=clean_method,
                holdings=len(holdings),
                symbols=len(symbols),
                lookback_days=clean_lookback,
                generated_at=generated_at,
                optimization={
                    "diagnostics": {
                        "history": history_stats,
                    },
                },
                message=(
                    "Insufficient historical data. At least two holdings "
                    f"must have {MIN_HISTORY_ROWS} or more usable prices."
                ),
            )

        returns = self._build_returns(
            price_cache=price_cache,
            symbols=symbols,
        )

        if returns is None or returns.empty:
            return self._failure(
                portfolio_id=clean_portfolio_id,
                portfolio_name=portfolio_name,
                method=clean_method,
                holdings=len(holdings),
                symbols=len(symbols),
                lookback_days=clean_lookback,
                generated_at=generated_at,
                optimization={
                    "diagnostics": {
                        "history": history_stats,
                    },
                },
                message=(
                    "Unable to construct an overlapping returns matrix "
                    "from the available price history."
                ),
            )

        if returns.shape[1] < 2:
            return self._failure(
                portfolio_id=clean_portfolio_id,
                portfolio_name=portfolio_name,
                method=clean_method,
                holdings=len(holdings),
                symbols=len(symbols),
                lookback_days=clean_lookback,
                generated_at=generated_at,
                optimization={
                    "diagnostics": {
                        "history": history_stats,
                        "returns_rows": int(returns.shape[0]),
                        "returns_assets": int(returns.shape[1]),
                    },
                },
                message=(
                    "Portfolio must contain at least two assets with "
                    "overlapping returns."
                ),
            )

        try:
            optimization_result, frontier = self._run_optimizer(
                returns=returns,
                method=clean_method,
            )
        except Exception:
            logger.exception(
                "Optimizer execution failed: portfolio=%s method=%s",
                clean_portfolio_id,
                clean_method,
            )
            return self._failure(
                portfolio_id=clean_portfolio_id,
                portfolio_name=portfolio_name,
                method=clean_method,
                holdings=len(holdings),
                symbols=len(symbols),
                lookback_days=clean_lookback,
                generated_at=generated_at,
                optimization={
                    "diagnostics": {
                        "history": history_stats,
                        "returns_rows": int(returns.shape[0]),
                        "returns_assets": int(returns.shape[1]),
                    },
                },
                message="Optimization engine failed.",
            )

        if not optimization_result:
            return self._failure(
                portfolio_id=clean_portfolio_id,
                portfolio_name=portfolio_name,
                method=clean_method,
                holdings=len(holdings),
                symbols=len(symbols),
                lookback_days=clean_lookback,
                generated_at=generated_at,
                optimization={
                    "diagnostics": {
                        "history": history_stats,
                        "returns_rows": int(returns.shape[0]),
                        "returns_assets": int(returns.shape[1]),
                    },
                },
                message="Optimizer did not produce a valid result.",
            )

        report = self._build_report(
            result=optimization_result,
            frontier=frontier,
            holdings=holdings,
            requested_symbols=symbols,
            returns=returns,
            history_stats=history_stats,
            method=clean_method,
        )

        logger.info(
            "Portfolio optimization completed: portfolio=%s method=%s "
            "optimized_assets=%s",
            clean_portfolio_id,
            clean_method,
            report.get("diagnostics", {}).get("optimized_asset_count"),
        )

        return OptimizationResult(
            success=True,
            portfolio_id=clean_portfolio_id,
            portfolio_name=portfolio_name,
            method=clean_method,
            generated_at=generated_at,
            holdings=len(holdings),
            symbols=len(symbols),
            lookback_days=clean_lookback,
            optimization=report,
            frontier=self._normalize_frontier(frontier),
            message="Optimization completed successfully.",
        )

    def self_test(
        self,
        portfolio_id: str,
        *,
        method: str = METHOD_MAX_SHARPE,
        lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    ) -> Dict[str, Any]:
        """Execute a lightweight end-to-end validation for one portfolio."""
        result = self.optimize(
            portfolio_id=portfolio_id,
            method=method,
            lookback_days=lookback_days,
        )

        return {
            "success": result.success,
            "message": result.message,
            "portfolio_id": result.portfolio_id,
            "portfolio": result.portfolio_name,
            "holdings": result.holdings,
            "symbols": result.symbols,
            "method": result.method,
            "lookback_days": result.lookback_days,
        }

    # ========================================================
    # Portfolio and Holdings
    # ========================================================

    def _load_portfolio(
        self,
        portfolio_id: str,
    ) -> Optional[Dict[str, Any]]:
        sql = text(
            """
            SELECT
                id,
                name,
                tenant_id,
                created_at
            FROM portfolios
            WHERE id = :portfolio_id
            LIMIT 1
            """
        )

        row = self.db.execute(
            sql,
            {"portfolio_id": portfolio_id},
        ).mappings().first()

        return dict(row) if row else None

    def _load_holdings(
            self,
            portfolio_id: str,
    ) -> pd.DataFrame:
        """
        Loads normalized holdings from the Portfolio Service.

        This avoids direct SQL and ensures optimization always
        operates on the same portfolio state seen by the UI,
        API and Trading Engine.
        """

        try:

            portfolio = self.portfolio_service.get_portfolio(
                portfolio_id=portfolio_id,
            )

            if portfolio is None:
                return pd.DataFrame()

            holdings = (
                    portfolio.get("positions")
                    or portfolio.get("holdings")
                    or []
            )

            if not holdings:
                return pd.DataFrame()

            rows = []

            for position in holdings:

                symbol = (
                        position.get("symbol")
                        or position.get("ticker")
                )

                if not symbol:
                    continue

                qty = (
                        position.get("qty")
                        or position.get("quantity")
                        or 0
                )

                if qty <= 0:
                    continue

                rows.append(
                    {
                        "symbol": symbol.upper(),

                        "qty": float(qty),

                        "average_cost":
                            float(
                                position.get(
                                    "average_cost",
                                    0,
                                )
                            ),

                        "market_value":
                            float(
                                position.get(
                                    "market_value",
                                    0,
                                )
                            ),

                        "unrealized_pl":
                            float(
                                position.get(
                                    "unrealized_pl",
                                    0,
                                )
                            ),

                        "sector":
                            position.get(
                                "sector"
                            ),

                        "asset_type":
                            position.get(
                                "asset_type",
                                "Equity",
                            ),

                        "currency":
                            position.get(
                                "currency",
                                "USD",
                            ),
                    }
                )

            if not rows:
                return pd.DataFrame()

            df = pd.DataFrame(rows)

            if "market_value" in df.columns:
                df = df.sort_values(
                    "market_value",
                    ascending=False,
                )

            return df.reset_index(
                drop=True,
            )

        except Exception:

            logger.exception(
                "Unable to load portfolio holdings."
            )

            return pd.DataFrame()

    def _extract_symbols(
        self,
        holdings: pd.DataFrame,
    ) -> List[str]:
        if holdings is None or holdings.empty or "symbol" not in holdings.columns:
            return []

        symbols: List[str] = []
        seen = set()

        for raw_symbol in holdings["symbol"].tolist():
            symbol = str(raw_symbol or "").upper().strip()
            if not symbol or symbol in seen:
                continue

            seen.add(symbol)
            symbols.append(symbol)

        return symbols

    # ========================================================
    # Historical Prices
    # ========================================================

    def _load_price_history(
        self,
        *,
        symbols: Sequence[str],
        lookback_days: int,
    ) -> Dict[str, List[float]]:
        """
        Load normalized closing-price lists through the market-data service.

        Failed symbols are logged and skipped so one unavailable provider or
        ticker does not abort the full portfolio request.
        """
        period = self._period_for_lookback(lookback_days)
        price_cache: Dict[str, List[float]] = {}

        for symbol in symbols:
            try:
                history = get_price_history(
                    db=self.db,
                    symbol=symbol,
                    period=period,
                    interval="1d",
                    force_refresh=False,
                )
                closes = self._extract_closes(
                    history,
                    lookback_days=lookback_days,
                )

                if len(closes) < MIN_HISTORY_ROWS:
                    logger.warning(
                        "Insufficient history for %s: rows=%s required=%s",
                        symbol,
                        len(closes),
                        MIN_HISTORY_ROWS,
                    )
                    continue

                price_cache[symbol] = closes

            except Exception:
                logger.exception(
                    "Unable to load market history for %s.",
                    symbol,
                )

        return price_cache

    def _extract_closes(
        self,
        history: Any,
        *,
        lookback_days: int,
    ) -> List[float]:
        if history is None:
            return []

        if isinstance(history, pd.DataFrame):
            frame = history.copy()

            if frame.empty:
                return []

            close_column = self._find_column(
                frame.columns,
                candidates=("Close", "close", "adj_close", "Adj Close"),
            )
            if close_column is None:
                return []

            date_column = self._find_column(
                frame.columns,
                candidates=("Date", "date", "datetime", "timestamp", "asof"),
            )

            if date_column is not None:
                frame[date_column] = pd.to_datetime(
                    frame[date_column],
                    errors="coerce",
                )
                frame = frame.sort_values(date_column)

            values = pd.to_numeric(
                frame[close_column],
                errors="coerce",
            )

        elif isinstance(history, pd.Series):
            values = pd.to_numeric(history, errors="coerce")

        elif isinstance(history, Mapping):
            raw_values = (
                history.get("Close")
                or history.get("close")
                or history.get("prices")
                or []
            )
            values = pd.to_numeric(
                pd.Series(raw_values),
                errors="coerce",
            )

        elif isinstance(history, Sequence) and not isinstance(
            history,
            (str, bytes),
        ):
            values = pd.to_numeric(
                pd.Series(list(history)),
                errors="coerce",
            )

        else:
            return []

        clean = values.replace([float("inf"), float("-inf")], pd.NA).dropna()
        clean = clean[clean > 0]

        if clean.empty:
            return []

        return [
            float(value)
            for value in clean.tail(lookback_days).tolist()
        ]

    # ========================================================
    # Returns Matrix
    # ========================================================

    def _build_returns(
        self,
        *,
        price_cache: Dict[str, List[float]],
        symbols: Sequence[str],
    ) -> Optional[pd.DataFrame]:
        returns = _build_return_matrix(
            price_cache,
            list(symbols),
        )

        if returns is None or not isinstance(returns, pd.DataFrame):
            return None

        if returns.empty:
            return None

        returns = returns.replace(
            [float("inf"), float("-inf")],
            pd.NA,
        ).dropna(how="any")

        if returns.empty:
            return None

        return returns

    # ========================================================
    # Optimizer
    # ========================================================

    def _run_optimizer(
        self,
        *,
        returns: pd.DataFrame,
        method: str,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[pd.DataFrame]]:
        if method == METHOD_MAX_SHARPE:
            result, frontier = optimize_max_sharpe(returns)

        elif method == METHOD_MIN_VOLATILITY:
            result, frontier = optimize_min_volatility(returns)

        elif method == METHOD_RISK_PARITY:
            result = optimize_risk_parity(returns)
            frontier = None

        else:
            raise ValueError(f"Unsupported optimization method: {method}")

        normalized_result = self._normalize_optimizer_result(result)
        normalized_frontier = self._normalize_frontier(frontier)

        return normalized_result, normalized_frontier

    def _normalize_optimizer_result(
        self,
        result: Any,
    ) -> Optional[Dict[str, Any]]:
        if result is None:
            return None

        if isinstance(result, pd.Series):
            result = result.to_dict()

        if not isinstance(result, Mapping):
            return None

        normalized: Dict[str, Any] = {}

        for key, value in result.items():
            scalar = _safe_float(value)
            if scalar is None:
                continue

            normalized[str(key)] = scalar

        required_metrics = {"Return", "Volatility", "Sharpe"}
        if not required_metrics.issubset(normalized):
            return None

        weights = {
            key: value
            for key, value in normalized.items()
            if key not in required_metrics
        }

        if len(weights) < 2:
            return None

        total_weight = sum(
            max(float(value), 0.0)
            for value in weights.values()
        )

        if total_weight <= 0:
            return None

        for symbol, weight in weights.items():
            normalized[symbol] = max(float(weight), 0.0) / total_weight

        return normalized

    def _normalize_frontier(
        self,
        frontier: Any,
    ) -> Optional[pd.DataFrame]:
        if frontier is None:
            return None

        try:
            if isinstance(frontier, pd.DataFrame):
                frame = frontier.copy()
            else:
                frame = pd.DataFrame(frontier)

            if frame.empty:
                return None

            frame = frame.replace(
                [float("inf"), float("-inf")],
                pd.NA,
            )

            for column in frame.columns:
                if pd.api.types.is_numeric_dtype(frame[column]):
                    frame[column] = pd.to_numeric(
                        frame[column],
                        errors="coerce",
                    )

            return frame.reset_index(drop=True)

        except Exception:
            logger.exception("Unable to normalize efficient frontier.")
            return None

    # ========================================================
    # Report Builder
    # ========================================================

    def _build_report(
        self,
        *,
        result: Dict[str, Any],
        frontier: Optional[pd.DataFrame],
        holdings: pd.DataFrame,
        requested_symbols: Sequence[str],
        returns: pd.DataFrame,
        history_stats: Dict[str, Any],
        method: str,
    ) -> Dict[str, Any]:
        expected_return = _safe_float(result.get("Return"))
        expected_volatility = _safe_float(result.get("Volatility"))
        sharpe_ratio = _safe_float(result.get("Sharpe"))

        metric_keys = {"Return", "Volatility", "Sharpe"}
        weights = {
            str(symbol): float(weight)
            for symbol, raw_weight in result.items()
            if symbol not in metric_keys
            if (weight := _safe_float(raw_weight)) is not None
        }

        allocation = [
            {
                "symbol": symbol,
                "weight": round(weight, 8),
                "weight_pct": round(weight * 100.0, 4),
            }
            for symbol, weight in sorted(
                weights.items(),
                key=lambda item: item[1],
                reverse=True,
            )
        ]

        current_weights = self._current_weight_map(holdings)
        recommendations = self._build_recommendations(
            allocation=allocation,
            current_weights=current_weights,
        )

        optimized_symbols = list(weights)
        omitted_symbols = [
            symbol
            for symbol in requested_symbols
            if symbol not in optimized_symbols
        ]

        frontier_rows = _dataframe_records(frontier)

        statistics = {
            "expected_return": expected_return,
            "expected_return_pct": _percent(expected_return),
            "expected_volatility": expected_volatility,
            "expected_volatility_pct": _percent(expected_volatility),
            "sharpe_ratio": sharpe_ratio,
            "risk_adjusted_return": (
                round(expected_return / expected_volatility, 6)
                if expected_return is not None
                and expected_volatility not in (None, 0.0)
                else None
            ),
        }

        diagnostics = {
            "method": method,
            "requested_asset_count": int(len(requested_symbols)),
            "optimized_asset_count": int(len(optimized_symbols)),
            "omitted_asset_count": int(len(omitted_symbols)),
            "omitted_symbols": omitted_symbols,
            "returns_rows": int(returns.shape[0]),
            "returns_assets": int(returns.shape[1]),
            "history": history_stats,
            "frontier_portfolios": int(len(frontier_rows)),
            "weight_sum": round(sum(weights.values()), 8),
        }

        summary = {
            "optimizer": "Portfolio Optimization Engine",
            "status": "SUCCESS",
            "method": method,
            "assets": int(len(weights)),
            "expected_return": expected_return,
            "volatility": expected_volatility,
            "sharpe_ratio": sharpe_ratio,
        }

        return _json_safe(
            {
                "summary": summary,
                "statistics": statistics,
                "weights": weights,
                "allocation": allocation,
                "current_weights": current_weights,
                "recommendations": recommendations,
                "efficient_frontier": frontier_rows,
                "diagnostics": diagnostics,
            }
        )

    def _current_weight_map(
        self,
        holdings: pd.DataFrame,
    ) -> Dict[str, float]:
        if holdings is None or holdings.empty:
            return {}

        work = holdings.copy()
        work["symbol"] = (
            work.get("symbol", pd.Series(dtype="object"))
            .fillna("")
            .astype(str)
            .str.upper()
            .str.strip()
        )

        if "market_value" in work.columns:
            market_values = pd.to_numeric(
                work["market_value"],
                errors="coerce",
            ).fillna(0.0)
        else:
            quantity = pd.to_numeric(
                work.get("qty", 0.0),
                errors="coerce",
            ).fillna(0.0)
            average_cost = pd.to_numeric(
                work.get("average_cost", 0.0),
                errors="coerce",
            ).fillna(0.0)
            market_values = quantity * average_cost

        work["_market_value"] = market_values.clip(lower=0.0)
        grouped = work.groupby("symbol")["_market_value"].sum()
        grouped = grouped[grouped.index != ""]

        total = float(grouped.sum())
        if total <= 0:
            return {}

        return {
            str(symbol): round(float(value) / total, 8)
            for symbol, value in grouped.items()
        }

    def _build_recommendations(
        self,
        *,
        allocation: Sequence[Dict[str, Any]],
        current_weights: Mapping[str, float],
    ) -> List[Dict[str, Any]]:
        recommendations: List[Dict[str, Any]] = []

        for row in allocation:
            symbol = str(row.get("symbol") or "")
            target_weight = _safe_float(row.get("weight")) or 0.0
            current_weight = _safe_float(current_weights.get(symbol)) or 0.0
            delta = target_weight - current_weight

            if delta >= 0.02:
                action = "INCREASE"
            elif delta <= -0.02:
                action = "DECREASE"
            else:
                action = "HOLD"

            recommendations.append(
                {
                    "symbol": symbol,
                    "action": action,
                    "current_weight": round(current_weight, 8),
                    "current_weight_pct": round(current_weight * 100.0, 4),
                    "recommended_weight": round(target_weight, 8),
                    "recommended_weight_pct": round(
                        target_weight * 100.0,
                        4,
                    ),
                    "weight_change": round(delta, 8),
                    "weight_change_pct": round(delta * 100.0, 4),
                }
            )

        return recommendations

    # ========================================================
    # Diagnostics and Validation
    # ========================================================

    def _history_statistics(
        self,
        *,
        requested_symbols: Sequence[str],
        price_cache: Mapping[str, Sequence[float]],
    ) -> Dict[str, Any]:
        rows_by_symbol = {
            symbol: int(len(price_cache.get(symbol, [])))
            for symbol in requested_symbols
        }

        usable_symbols = [
            symbol
            for symbol, rows in rows_by_symbol.items()
            if rows >= MIN_HISTORY_ROWS
        ]

        missing_symbols = [
            symbol
            for symbol in requested_symbols
            if symbol not in usable_symbols
        ]

        row_counts = [
            rows_by_symbol[symbol]
            for symbol in usable_symbols
        ]

        return {
            "requested_symbols": int(len(requested_symbols)),
            "usable_symbols": int(len(usable_symbols)),
            "missing_symbols": missing_symbols,
            "rows_by_symbol": rows_by_symbol,
            "minimum_rows": min(row_counts) if row_counts else 0,
            "maximum_rows": max(row_counts) if row_counts else 0,
        }

    def _failure(
        self,
        *,
        portfolio_id: Optional[str],
        method: str,
        lookback_days: int,
        generated_at: str,
        message: str,
        portfolio_name: Optional[str] = None,
        holdings: int = 0,
        symbols: int = 0,
        optimization: Optional[Dict[str, Any]] = None,
    ) -> OptimizationResult:
        return OptimizationResult(
            success=False,
            portfolio_id=portfolio_id,
            portfolio_name=portfolio_name,
            method=method,
            generated_at=generated_at,
            holdings=int(holdings),
            symbols=int(symbols),
            lookback_days=int(lookback_days),
            optimization=_json_safe(optimization),
            frontier=None,
            message=message,
        )

    def _validate_portfolio_id(
        self,
        portfolio_id: Any,
    ) -> str:
        value = str(portfolio_id or "").strip()
        if not value:
            raise ValueError("portfolio_id is required.")

        if len(value) > 128:
            raise ValueError("portfolio_id is invalid.")

        return value

    def _normalize_method(
        self,
        method: Any,
    ) -> str:
        normalized = self._normalize_method_soft(method)
        if normalized not in SUPPORTED_METHODS:
            supported = ", ".join(sorted(SUPPORTED_METHODS))
            raise ValueError(
                f"Unsupported optimization method. Supported methods: "
                f"{supported}."
            )

        return normalized

    def _normalize_method_soft(
        self,
        method: Any,
    ) -> str:
        raw = str(method or METHOD_MAX_SHARPE).strip().lower()
        normalized = raw.replace("-", "_")
        return _METHOD_ALIASES.get(raw, normalized)

    def _normalize_lookback_days(
        self,
        lookback_days: Any,
    ) -> int:
        value = _safe_int(
            lookback_days,
            default=DEFAULT_LOOKBACK_DAYS,
        )

        if value < MIN_LOOKBACK_DAYS:
            raise ValueError(
                f"lookback_days must be at least {MIN_LOOKBACK_DAYS}."
            )

        if value > MAX_LOOKBACK_DAYS:
            raise ValueError(
                f"lookback_days cannot exceed {MAX_LOOKBACK_DAYS}."
            )

        return value

    def _period_for_lookback(
        self,
        lookback_days: int,
    ) -> str:
        if lookback_days <= 31:
            return "1mo"
        if lookback_days <= 93:
            return "3mo"
        if lookback_days <= 186:
            return "6mo"
        if lookback_days <= 366:
            return "1y"
        if lookback_days <= 731:
            return "2y"
        if lookback_days <= 1827:
            return "5y"
        return "10y"

    @staticmethod
    def _find_column(
        columns: Sequence[Any],
        *,
        candidates: Sequence[str],
    ) -> Optional[Any]:
        lookup = {
            str(column).lower().strip(): column
            for column in columns
        }

        for candidate in candidates:
            match = lookup.get(str(candidate).lower().strip())
            if match is not None:
                return match

        return None


# ============================================================
# Factory
# ============================================================

def get_portfolio_optimization_engine(
    db: Session,
) -> PortfolioOptimizationEngine:
    """Return a portfolio optimization engine for the supplied DB session."""
    return PortfolioOptimizationEngine(db=db)


# ============================================================
# Module Helpers
# ============================================================

def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _clean_optional_text(value: Any) -> Optional[str]:
    if value is None:
        return None

    text_value = str(value).strip()
    return text_value or None


def _safe_int(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None

    try:
        if hasattr(value, "item"):
            value = value.item()
    except Exception:
        pass

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(number):
        return None

    return number


def _percent(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return round(float(value) * 100.0, 4)


def _dataframe_records(
    frame: Optional[pd.DataFrame],
) -> List[Dict[str, Any]]:
    if frame is None:
        return []

    try:
        if not isinstance(frame, pd.DataFrame):
            frame = pd.DataFrame(frame)

        if frame.empty:
            return []

        return _json_safe(frame.to_dict(orient="records"))
    except Exception:
        logger.exception("Unable to serialize DataFrame records.")
        return []


def _json_safe(value: Any) -> Any:
    """Recursively normalize pandas, NumPy, datetime, and non-finite values."""
    if value is None:
        return None

    if isinstance(value, pd.DataFrame):
        return _dataframe_records(value)

    if isinstance(value, pd.Series):
        return _json_safe(value.to_dict())

    if isinstance(value, pd.Timestamp):
        if pd.isna(value):
            return None
        return value.isoformat()

    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, Mapping):
        return {
            str(key): _json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]

    try:
        if hasattr(value, "item"):
            return _json_safe(value.item())
    except Exception:
        pass

    if isinstance(value, float):
        return value if math.isfinite(value) else None

    try:
        if pd.isna(value):
            return None
    except Exception:
        pass

    return value


__all__ = [
    "DEFAULT_LOOKBACK_DAYS",
    "METHOD_MAX_SHARPE",
    "METHOD_MIN_VOLATILITY",
    "METHOD_RISK_PARITY",
    "OptimizationResult",
    "PortfolioOptimizationEngine",
    "SUPPORTED_METHODS",
    "get_portfolio_optimization_engine",
]