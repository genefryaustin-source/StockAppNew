"""
forex_execution_dashboard_service.py

Dashboard orchestration layer for the Forex execution workspace.

This service sits between the Streamlit dashboards and the execution
repository. It does not issue SQL directly. All persistence reads are
delegated to ForexExecutionRepository.

Primary consumers:

- forex_trading_desk_dashboard.py
- forex_execution_dashboard.py
- forex_workspace.py
- forex_master_workspace.py
- Executive AI panels
- Recent Activity panels
"""

from __future__ import annotations

import logging

from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from modules import db
from modules.forex.forex_execution_repository import (
    ForexExecutionRepository,
    get_forex_execution_repository,
)

logger = logging.getLogger(__name__)


class ForexExecutionDashboardService:
    """
    Builds normalized dashboard packets for Forex execution interfaces.

    The service intentionally separates dashboard orchestration from:

    - database access
    - broker execution
    - trade management
    - Streamlit rendering
    """

    def __init__(
        self,
        *,
        db=None,
        repository: Optional[ForexExecutionRepository] = None,
        analytics_engine=None,
    ) -> None:
        self.db = db

        self.repository = (
            repository
            if repository is not None
            else get_forex_execution_repository(db=db)
        )

        self.analytics_engine = analytics_engine

        if (
            self.repository is not None
            and db is not None
            and getattr(self.repository, "db", None) is None
        ):
            self.repository.set_db(db)

        logger.info(
            "ForexExecutionDashboardService initialized."
        )

    ####################################################################
    # Dependency Management
    ####################################################################

    def set_db(
        self,
        db,
    ) -> None:
        """
        Replace or attach the active SQLAlchemy session/connection.
        """

        self.db = db

        if self.repository is not None:
            self.repository.set_db(db)

        if self.analytics_engine is not None:
            setter = getattr(
                self.analytics_engine,
                "set_db",
                None,
            )

            if callable(setter):
                setter(db)

            elif hasattr(
                self.analytics_engine,
                "db",
            ):
                self.analytics_engine.db = db

    def set_repository(
        self,
        repository: ForexExecutionRepository,
    ) -> None:
        """
        Replace the execution repository dependency.
        """

        self.repository = repository

        if (
            self.repository is not None
            and self.db is not None
            and getattr(self.repository, "db", None) is None
        ):
            self.repository.set_db(self.db)

    def set_analytics_engine(
        self,
        analytics_engine,
    ) -> None:
        """
        Attach the execution analytics engine without creating a hard
        circular import between the service and analytics modules.
        """

        self.analytics_engine = analytics_engine

        if (
            analytics_engine is not None
            and self.db is not None
        ):
            setter = getattr(
                analytics_engine,
                "set_db",
                None,
            )

            if callable(setter):
                setter(self.db)

            elif hasattr(
                analytics_engine,
                "db",
            ):
                analytics_engine.db = self.db

    def has_database(
        self,
    ) -> bool:
        return (
            self.repository is not None
            and self.repository.has_database()
        )

    ####################################################################
    # Normalization Helpers
    ####################################################################

    @staticmethod
    def _safe_float(
        value: Any,
        default: float = 0.0,
    ) -> float:
        try:
            if value is None:
                return default

            return float(value)

        except (
            TypeError,
            ValueError,
        ):
            return default

    @staticmethod
    def _safe_int(
        value: Any,
        default: int = 0,
    ) -> int:
        try:
            if value is None:
                return default

            return int(value)

        except (
            TypeError,
            ValueError,
        ):
            return default

    @staticmethod
    def _normalize_symbol(
        row: Dict[str, Any],
    ) -> Optional[str]:
        value = (
            row.get("symbol")
            or row.get("pair")
            or row.get("instrument")
        )

        if value is None:
            return None

        return str(value).strip().upper()

    @staticmethod
    def _normalize_side(
        row: Dict[str, Any],
    ) -> Optional[str]:
        value = (
            row.get("side")
            or row.get("direction")
            or row.get("position_side")
        )

        if value is None:
            return None

        side = str(value).strip().upper()

        if side in {
            "LONG",
            "BUY",
        }:
            return "BUY"

        if side in {
            "SHORT",
            "SELL",
        }:
            return "SELL"

        return side

    @staticmethod
    def _normalize_status(
        row: Dict[str, Any],
    ) -> Optional[str]:
        value = (
            row.get("status")
            or row.get("order_status")
            or row.get("position_status")
            or row.get("event_type")
        )

        if value is None:
            return None

        return str(value).strip().upper()

    @staticmethod
    def _normalize_timestamp(
        row: Dict[str, Any],
    ) -> Any:
        return (
            row.get("event_time")
            or row.get("filled_at")
            or row.get("executed_at")
            or row.get("closed_at")
            or row.get("opened_at")
            or row.get("updated_at")
            or row.get("created_at")
            or row.get("timestamp")
        )

    def _normalize_order(
        self,
        row: Dict[str, Any],
    ) -> Dict[str, Any]:
        quantity = self._safe_float(
            row.get(
                "units",
                row.get(
                    "quantity",
                    row.get(
                        "requested_quantity",
                        0,
                    ),
                ),
            )
        )

        filled_quantity = self._safe_float(
            row.get(
                "filled_units",
                row.get(
                    "filled_quantity",
                    row.get(
                        "executed_quantity",
                        0,
                    ),
                ),
            )
        )

        return {
            **row,
            "symbol": self._normalize_symbol(row),
            "pair": (
                row.get("pair")
                or self._normalize_symbol(row)
            ),
            "side": self._normalize_side(row),
            "status": self._normalize_status(row),
            "quantity": quantity,
            "units": quantity,
            "filled_quantity": filled_quantity,
            "order_type": (
                row.get("order_type")
                or row.get("type")
            ),
            "price": self._safe_float(
                row.get(
                    "price",
                    row.get(
                        "execution_price",
                        row.get(
                            "fill_price",
                            row.get(
                                "limit_price",
                                0,
                            ),
                        ),
                    ),
                )
            ),
            "timestamp": self._normalize_timestamp(row),
        }

    def _normalize_position(
        self,
        row: Dict[str, Any],
    ) -> Dict[str, Any]:
        quantity = self._safe_float(
            row.get(
                "units",
                row.get(
                    "quantity",
                    row.get(
                        "remaining_quantity",
                        0,
                    ),
                ),
            )
        )

        entry_price = self._safe_float(
            row.get(
                "entry_price",
                row.get(
                    "average_entry_price",
                    row.get(
                        "avg_entry_price",
                        row.get(
                            "open_price",
                            0,
                        ),
                    ),
                ),
            )
        )

        current_price = self._safe_float(
            row.get(
                "current_price",
                row.get(
                    "market_price",
                    row.get(
                        "mark_price",
                        entry_price,
                    ),
                ),
            ),
            entry_price,
        )

        realized_pnl = self._safe_float(
            row.get(
                "realized_pnl",
                row.get(
                    "pnl",
                    row.get(
                        "profit_loss",
                        0,
                    ),
                ),
            )
        )

        unrealized_pnl = self._safe_float(
            row.get(
                "unrealized_pnl",
                row.get(
                    "floating_pnl",
                    0,
                ),
            )
        )

        return {
            **row,
            "symbol": self._normalize_symbol(row),
            "pair": (
                row.get("pair")
                or self._normalize_symbol(row)
            ),
            "side": self._normalize_side(row),
            "status": self._normalize_status(row),
            "quantity": quantity,
            "units": quantity,
            "entry_price": entry_price,
            "current_price": current_price,
            "exit_price": self._safe_float(
                row.get(
                    "exit_price",
                    row.get(
                        "close_price",
                        0,
                    ),
                )
            ),
            "realized_pnl": realized_pnl,
            "unrealized_pnl": unrealized_pnl,
            "opened_at": (
                row.get("opened_at")
                or row.get("created_at")
            ),
            "closed_at": row.get("closed_at"),
            "timestamp": self._normalize_timestamp(row),
        }

    def _normalize_activity(
        self,
        row: Dict[str, Any],
    ) -> Dict[str, Any]:
        event_type = (
            row.get("event_type")
            or row.get("type")
            or row.get("status")
            or "UNKNOWN"
        )

        quantity = self._safe_float(
            row.get(
                "units",
                row.get(
                    "quantity",
                    row.get(
                        "filled_quantity",
                        0,
                    ),
                ),
            )
        )

        price = self._safe_float(
            row.get(
                "execution_price",
                row.get(
                    "fill_price",
                    row.get(
                        "price",
                        row.get(
                            "entry_price",
                            row.get(
                                "exit_price",
                                0,
                            ),
                        ),
                    ),
                ),
            )
        )

        return {
            **row,
            "timestamp": self._normalize_timestamp(row),
            "event_type": str(event_type).strip().upper(),
            "event": str(event_type).strip().upper(),
            "symbol": self._normalize_symbol(row),
            "pair": (
                row.get("pair")
                or self._normalize_symbol(row)
            ),
            "side": self._normalize_side(row),
            "status": self._normalize_status(row),
            "quantity": quantity,
            "units": quantity,
            "price": price,
            "order_id": row.get("order_id"),
            "position_id": row.get("position_id"),
        }

    ####################################################################
    # Primary Dashboard Retrieval APIs
    ####################################################################

    def get_orders(
        self,
        *,
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        include_cancelled: bool = True,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        if self.repository is None:
            return []

        try:
            rows = self.repository.load_orders(
                account_id=account_id,
                portfolio_id=portfolio_id,
                include_cancelled=include_cancelled,
                limit=limit,
            )

            return [
                self._normalize_order(row)
                for row in rows
            ]

        except Exception:
            logger.exception(
                "Unable to load Forex execution orders."
            )

            return []

    def get_open_positions(
        self,
        *,
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        if self.repository is None:
            return []

        try:
            rows = self.repository.load_open_positions(
                account_id=account_id,
                portfolio_id=portfolio_id,
                limit=limit,
            )

            return [
                self._normalize_position(row)
                for row in rows
            ]

        except Exception:
            logger.exception(
                "Unable to load open Forex positions."
            )

            return []

    def get_closed_positions(
        self,
        *,
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        if self.repository is None:
            return []

        try:
            rows = self.repository.load_closed_positions(
                account_id=account_id,
                portfolio_id=portfolio_id,
                limit=limit,
            )

            return [
                self._normalize_position(row)
                for row in rows
            ]

        except Exception:
            logger.exception(
                "Unable to load closed Forex positions."
            )

            return []

    def get_execution_history(
        self,
        *,
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        if self.repository is None:
            return []

        try:
            rows = self.repository.load_execution_history(
                account_id=account_id,
                portfolio_id=portfolio_id,
                limit=limit,
            )

            return [
                self._normalize_activity(row)
                for row in rows
            ]

        except Exception:
            logger.exception(
                "Unable to load Forex execution history."
            )

            return []

    def get_recent_activity(
        self,
        *,
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Return the most recent normalized execution events.

        This method intentionally returns the same stable data shape used by
        the Recent Activity Streamlit section.
        """

        rows = self.get_execution_history(
            account_id=account_id,
            portfolio_id=portfolio_id,
            limit=limit,
        )

        try:
            return sorted(
                rows,
                key=lambda row: (
                    row.get("timestamp") is not None,
                    str(row.get("timestamp") or ""),
                ),
                reverse=True,
            )[:limit]

        except Exception:
            return rows[:limit]

    def get_execution_summary(
        self,
        *,
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if self.repository is None:
            return self._empty_summary()

        try:
            statistics = (
                self.repository.load_execution_statistics(
                    account_id=account_id,
                    portfolio_id=portfolio_id,
                )
            )

            performance = (
                self.repository.load_performance_metrics(
                    account_id=account_id,
                    portfolio_id=portfolio_id,
                )
            )

            quality = (
                self.repository.load_execution_quality(
                    account_id=account_id,
                    portfolio_id=portfolio_id,
                )
            )

            exposure = (
                self.repository.load_portfolio_exposure(
                    account_id=account_id,
                    portfolio_id=portfolio_id,
                )
            )

            return {
                "statistics": statistics or {},
                "performance": performance or {},
                "quality": quality or {},
                "exposure": exposure or [],
            }

        except Exception:
            logger.exception(
                "Unable to build Forex execution summary."
            )

            return self._empty_summary()

    ####################################################################
    # KPI Cards
    ####################################################################

    def get_dashboard_cards(
        self,
        *,
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Build normalized KPI cards for the execution dashboard.
        """

        summary = self.get_execution_summary(
            account_id=account_id,
            portfolio_id=portfolio_id,
        )

        statistics = summary.get(
            "statistics",
            {},
        )

        performance = summary.get(
            "performance",
            {},
        )

        quality = summary.get(
            "quality",
            {},
        )

        total_orders = self._safe_int(
            statistics.get("total_orders")
        )

        filled_orders = self._safe_int(
            statistics.get("filled_orders")
        )

        pending_orders = self._safe_int(
            statistics.get("pending_orders")
        )

        rejected_orders = self._safe_int(
            statistics.get("rejected_orders")
        )

        open_positions = self._safe_int(
            statistics.get("open_positions")
        )

        closed_positions = self._safe_int(
            statistics.get("closed_positions")
        )

        total_trades = self._safe_int(
            performance.get("total_trades")
        )

        winning_trades = self._safe_int(
            performance.get("winning_trades")
        )

        losing_trades = self._safe_int(
            performance.get("losing_trades")
        )

        win_rate = self._safe_float(
            performance.get("win_rate")
        )

        net_profit = self._safe_float(
            performance.get("net_profit")
        )

        profit_factor = performance.get(
            "profit_factor"
        )

        fill_rate = self._safe_float(
            quality.get("fill_rate")
        )

        average_slippage = quality.get(
            "average_slippage"
        )

        average_latency = quality.get(
            "average_latency_seconds"
        )

        return {
            "total_orders": {
                "label": "Total Orders",
                "value": total_orders,
                "delta": None,
            },

            "filled_orders": {
                "label": "Filled Orders",
                "value": filled_orders,
                "delta": None,
            },

            "pending_orders": {
                "label": "Pending Orders",
                "value": pending_orders,
                "delta": None,
            },

            "rejected_orders": {
                "label": "Rejected Orders",
                "value": rejected_orders,
                "delta": None,
            },

            "open_positions": {
                "label": "Open Positions",
                "value": open_positions,
                "delta": None,
            },

            "closed_positions": {
                "label": "Closed Positions",
                "value": closed_positions,
                "delta": None,
            },

            "total_trades": {
                "label": "Closed Trades",
                "value": total_trades,
                "delta": None,
            },

            "winning_trades": {
                "label": "Winning Trades",
                "value": winning_trades,
                "delta": None,
            },

            "losing_trades": {
                "label": "Losing Trades",
                "value": losing_trades,
                "delta": None,
            },

            "win_rate": {
                "label": "Win Rate",
                "value": win_rate,
                "formatted": f"{win_rate:.2f}%",
                "delta": None,
            },

            "net_profit": {
                "label": "Net Realized P&L",
                "value": net_profit,
                "formatted": f"${net_profit:,.2f}",
                "delta": None,
            },

            "profit_factor": {
                "label": "Profit Factor",
                "value": profit_factor,
                "formatted": (
                    f"{self._safe_float(profit_factor):.2f}"
                    if profit_factor is not None
                    else "N/A"
                ),
                "delta": None,
            },

            "fill_rate": {
                "label": "Fill Rate",
                "value": fill_rate,
                "formatted": f"{fill_rate:.2f}%",
                "delta": None,
            },

            "average_slippage": {
                "label": "Average Slippage",
                "value": average_slippage,
                "formatted": (
                    f"{self._safe_float(average_slippage):.6f}"
                    if average_slippage is not None
                    else "N/A"
                ),
                "delta": None,
            },

            "average_latency": {
                "label": "Average Fill Latency",
                "value": average_latency,
                "formatted": (
                    f"{self._safe_float(average_latency):.3f}s"
                    if average_latency is not None
                    else "N/A"
                ),
                "delta": None,
            },
        }

    ####################################################################
    # Order Status Distribution
    ####################################################################

    def get_order_status_distribution(
        self,
        *,
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        limit: int = 5000,
    ) -> List[Dict[str, Any]]:
        orders = self.get_orders(
            account_id=account_id,
            portfolio_id=portfolio_id,
            include_cancelled=True,
            limit=limit,
        )

        counts: Dict[str, int] = {}

        for order in orders:
            status = (
                order.get("status")
                or "UNKNOWN"
            )

            status = str(
                status
            ).strip().upper()

            counts[status] = (
                counts.get(status, 0)
                + 1
            )

        total = len(orders)

        rows = []

        for status, count in counts.items():
            percentage = (
                count / total * 100.0
                if total
                else 0.0
            )

            rows.append(
                {
                    "status": status,
                    "count": count,
                    "percentage": percentage,
                }
            )

        return sorted(
            rows,
            key=lambda row: row["count"],
            reverse=True,
        )

    ####################################################################
    # Side Distribution
    ####################################################################

    def get_side_distribution(
        self,
        *,
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        limit: int = 5000,
    ) -> List[Dict[str, Any]]:
        history = self.get_execution_history(
            account_id=account_id,
            portfolio_id=portfolio_id,
            limit=limit,
        )

        counts = {
            "BUY": 0,
            "SELL": 0,
            "UNKNOWN": 0,
        }

        volume = {
            "BUY": 0.0,
            "SELL": 0.0,
            "UNKNOWN": 0.0,
        }

        for row in history:
            side = (
                row.get("side")
                or "UNKNOWN"
            )

            side = str(
                side
            ).strip().upper()

            if side not in counts:
                side = "UNKNOWN"

            counts[side] += 1

            quantity = abs(
                self._safe_float(
                    row.get(
                        "quantity",
                        row.get(
                            "units",
                            0,
                        ),
                    )
                )
            )

            volume[side] += quantity

        return [
            {
                "side": side,
                "executions": counts[side],
                "volume": volume[side],
            }
            for side in (
                "BUY",
                "SELL",
                "UNKNOWN",
            )
            if counts[side] > 0
        ]

    ####################################################################
    # Pair Distribution
    ####################################################################

    def get_pair_distribution(
        self,
        *,
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        limit: int = 5000,
    ) -> List[Dict[str, Any]]:
        if self.repository is None:
            return []

        try:
            rows = self.repository.load_symbol_statistics(
                account_id=account_id,
                portfolio_id=portfolio_id,
            )

            return [
                {
                    "pair": (
                        row.get("pair")
                        or row.get("symbol")
                        or "UNKNOWN"
                    ),
                    "symbol": (
                        row.get("symbol")
                        or row.get("pair")
                        or "UNKNOWN"
                    ),
                    "executions": self._safe_int(
                        row.get("executions")
                    ),
                    "buy_orders": self._safe_int(
                        row.get("buy_orders")
                    ),
                    "sell_orders": self._safe_int(
                        row.get("sell_orders")
                    ),
                    "volume": self._safe_float(
                        row.get("volume")
                    ),
                }
                for row in rows[:limit]
            ]

        except Exception:
            logger.exception(
                "Unable to build Forex pair distribution."
            )

            return []

    ####################################################################
    # Strategy Distribution
    ####################################################################

    def get_strategy_distribution(
        self,
        *,
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if self.repository is None:
            return []

        try:
            rows = self.repository.load_strategy_statistics(
                account_id=account_id,
                portfolio_id=portfolio_id,
            )

            return [
                {
                    "strategy": (
                        row.get("strategy")
                        or "Manual"
                    ),
                    "executions": self._safe_int(
                        row.get("executions")
                    ),
                    "volume": self._safe_float(
                        row.get("volume")
                    ),
                }
                for row in rows
            ]

        except Exception:
            logger.exception(
                "Unable to build Forex strategy distribution."
            )

            return []

    ####################################################################
    # Daily Execution Chart
    ####################################################################

    def get_daily_execution_chart(
        self,
        *,
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if self.repository is None:
            return []

        try:
            rows = self.repository.load_daily_statistics(
                account_id=account_id,
                portfolio_id=portfolio_id,
            )

            return [
                {
                    "date": row.get("date"),
                    "executions": self._safe_int(
                        row.get("executions")
                    ),
                    "volume": self._safe_float(
                        row.get("volume")
                    ),
                }
                for row in rows
            ]

        except Exception:
            logger.exception(
                "Unable to build daily Forex execution chart."
            )

            return []

    ####################################################################
    # Realized P&L Chart
    ####################################################################

    def get_realized_pnl_chart(
        self,
        *,
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        limit: int = 5000,
    ) -> List[Dict[str, Any]]:
        closed_positions = self.get_closed_positions(
            account_id=account_id,
            portfolio_id=portfolio_id,
            limit=limit,
        )

        rows = []

        cumulative_pnl = 0.0

        sorted_positions = sorted(
            closed_positions,
            key=lambda row: str(
                row.get("closed_at")
                or row.get("timestamp")
                or ""
            ),
        )

        for index, row in enumerate(
            sorted_positions,
            start=1,
        ):
            realized_pnl = self._safe_float(
                row.get("realized_pnl")
            )

            cumulative_pnl += realized_pnl

            rows.append(
                {
                    "trade_number": index,
                    "closed_at": (
                        row.get("closed_at")
                        or row.get("timestamp")
                    ),
                    "pair": (
                        row.get("pair")
                        or row.get("symbol")
                    ),
                    "side": row.get("side"),
                    "realized_pnl": realized_pnl,
                    "cumulative_pnl": cumulative_pnl,
                }
            )

        return rows

    ####################################################################
    # Charts Packet
    ####################################################################

    def get_charts(
        self,
        *,
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        return {
            "daily_executions": (
                self.get_daily_execution_chart(
                    account_id=account_id,
                    portfolio_id=portfolio_id,
                )
            ),

            "realized_pnl": (
                self.get_realized_pnl_chart(
                    account_id=account_id,
                    portfolio_id=portfolio_id,
                )
            ),
        }

    ####################################################################
    # Distribution Packet
    ####################################################################

    def get_distributions(
        self,
        *,
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        return {
            "order_status": (
                self.get_order_status_distribution(
                    account_id=account_id,
                    portfolio_id=portfolio_id,
                )
            ),

            "side": (
                self.get_side_distribution(
                    account_id=account_id,
                    portfolio_id=portfolio_id,
                )
            ),

            "pair": (
                self.get_pair_distribution(
                    account_id=account_id,
                    portfolio_id=portfolio_id,
                )
            ),

            "strategy": (
                self.get_strategy_distribution(
                    account_id=account_id,
                    portfolio_id=portfolio_id,
                )
            ),
        }


    ####################################################################
    # Complete Dashboard Packet
    ####################################################################

    def get_dashboard_data(
        self,
        *,
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        orders_limit: int = 500,
        positions_limit: int = 500,
        activity_limit: int = 100,
    ) -> Dict[str, Any]:
        """
        Build the complete stable packet consumed by Forex dashboards.

        Important:

        Recent Activity should be read from:

            data.get("execution_history", [])

        and not from a nested portfolio dictionary.
        """

        orders = self.get_orders(
            account_id=account_id,
            portfolio_id=portfolio_id,
            include_cancelled=True,
            limit=orders_limit,
        )

        open_positions = self.get_open_positions(
            account_id=account_id,
            portfolio_id=portfolio_id,
            limit=positions_limit,
        )

        closed_positions = self.get_closed_positions(
            account_id=account_id,
            portfolio_id=portfolio_id,
            limit=positions_limit,
        )

        execution_history = self.get_recent_activity(
            account_id=account_id,
            portfolio_id=portfolio_id,
            limit=activity_limit,
        )

        summary = self.get_execution_summary(
            account_id=account_id,
            portfolio_id=portfolio_id,
        )

        statistics = summary.get(
            "statistics",
            {},
        )

        performance = summary.get(
            "performance",
            {},
        )

        quality = summary.get(
            "quality",
            {},
        )

        exposure = summary.get(
            "exposure",
            [],
        )

        return {
            "account_id": account_id,
            "portfolio_id": portfolio_id,

            "orders": orders,
            "open_orders": [
                row
                for row in orders
                if row.get("status") in {
                    "NEW",
                    "OPEN",
                    "PENDING",
                    "WORKING",
                    "PARTIALLY_FILLED",
                }
            ],
            "completed_orders": [
                row
                for row in orders
                if row.get("status") in {
                    "FILLED",
                    "EXECUTED",
                    "CLOSED",
                }
            ],

            "positions": open_positions,
            "open_positions": open_positions,
            "closed_positions": closed_positions,

            "execution_history": execution_history,
            "recent_activity": execution_history,
            "timeline": execution_history,

            "statistics": statistics,
            "performance": performance,
            "quality": quality,
            "exposure": exposure,

            "summary": summary,

            "counts": {
                "orders": len(orders),
                "open_positions": len(open_positions),
                "closed_positions": len(closed_positions),
                "execution_events": len(execution_history),
            },

            "cards": self.get_dashboard_cards(
                account_id=account_id,
                portfolio_id=portfolio_id,
            ),

            "charts": self.get_charts(
                account_id=account_id,
                portfolio_id=portfolio_id,
            ),

            "distributions": self.get_distributions(
                account_id=account_id,
                portfolio_id=portfolio_id,
            ),

            "repository_health": self.get_repository_health(),

            "errors": [],
        }

    # Backward-compatible aliases used by dashboard modules.

    def dashboard_data(
        self,
        *,
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        orders_limit: int = 500,
        positions_limit: int = 500,
        activity_limit: int = 100,
    ) -> Dict[str, Any]:
        return self.get_dashboard_data(
            account_id=account_id,
            portfolio_id=portfolio_id,
            orders_limit=orders_limit,
            positions_limit=positions_limit,
            activity_limit=activity_limit,
        )

    def build_dashboard_packet(
        self,
        *,
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        orders_limit: int = 500,
        positions_limit: int = 500,
        activity_limit: int = 100,
    ) -> Dict[str, Any]:
        return self.get_dashboard_data(
            account_id=account_id,
            portfolio_id=portfolio_id,
            orders_limit=orders_limit,
            positions_limit=positions_limit,
            activity_limit=activity_limit,
        )

    ####################################################################
    # Repository Health
    ####################################################################

    def get_repository_health(
        self,
    ) -> Dict[str, Any]:
        if self.repository is None:
            return {
                "connected": False,
                "repository": None,
                "health": {},
            }

        try:
            return self.repository.status()

        except Exception:
            logger.exception(
                "Unable to retrieve Forex execution repository health."
            )

            return {
                "connected": False,
                "repository": self.repository.__class__.__name__,
                "health": {},
            }

    @staticmethod
    def _empty_summary(
    ) -> Dict[str, Any]:
        return {
            "statistics": {
                "total_orders": 0,
                "filled_orders": 0,
                "pending_orders": 0,
                "cancelled_orders": 0,
                "rejected_orders": 0,
                "open_positions": 0,
                "closed_positions": 0,
            },
            "performance": {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "gross_profit": 0.0,
                "gross_loss": 0.0,
                "net_profit": 0.0,
                "largest_win": 0.0,
                "largest_loss": 0.0,
                "profit_factor": None,
                "average_trade_duration_seconds": None,
            },
            "quality": {
                "fills": 0,
                "partial_fills": 0,
                "average_slippage": None,
                "average_latency_seconds": None,
                "fill_rate": 0.0,
            },
            "exposure": [],
        }


#######################################################################
# Singleton Factory
#######################################################################

_FOREX_EXECUTION_DASHBOARD_SERVICE = None


def get_forex_execution_dashboard_service(
    db=None,
    *,
    repository=None,
    analytics_engine=None,
):

    global _FOREX_EXECUTION_DASHBOARD_SERVICE

    if _FOREX_EXECUTION_DASHBOARD_SERVICE is None:

        _FOREX_EXECUTION_DASHBOARD_SERVICE = (
            ForexExecutionDashboardService(
                db=db,
                repository=repository,
                analytics_engine=analytics_engine,
            )
        )

    else:

        if db is not None:
            _FOREX_EXECUTION_DASHBOARD_SERVICE.set_db(db)

        if repository is not None:
            _FOREX_EXECUTION_DASHBOARD_SERVICE.set_repository(repository)

        if analytics_engine is not None:
            _FOREX_EXECUTION_DASHBOARD_SERVICE.set_analytics_engine(
                analytics_engine
            )

    return _FOREX_EXECUTION_DASHBOARD_SERVICE