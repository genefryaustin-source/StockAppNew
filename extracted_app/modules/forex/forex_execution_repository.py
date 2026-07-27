"""
forex_execution_repository.py

Institutional Forex Execution Repository

This repository is the single data access layer for:

• Execution History
• Orders
• Positions
• Closed Positions
• Execution Events
• Performance Statistics
• Execution Analytics
• AI Execution Reporting

Used by:

- forex_execution_dashboard_service.py
- forex_execution_analytics_engine.py
- forex_execution_quality_engine.py
- forex_trade_management_engine.py
- forex_ai_trade_review.py
"""

from __future__ import annotations

import logging

from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


class ForexExecutionRepository:
    """
    Institutional repository for all Forex execution data.
    """

    ####################################################################
    # Construction
    ####################################################################

    def __init__(self, db=None):

        self.db = db

        #
        # Primary execution tables
        #

        self.execution_events_table = "execution_events"

        self.execution_orders_table = "execution_orders"

        self.execution_positions_table = "execution_positions"

        #
        # Legacy compatibility
        #

        self.trade_orders_table = "forex_trade_orders"

        self.positions_table = "forex_positions"

        self.closed_positions_table = "closed_trades"

        self.executions_table = "forex_executions"

        self.fills_table = "forex_fills"

        logger.info(
            "ForexExecutionRepository initialized."
        )

    ####################################################################
    # DB Helpers
    ####################################################################

    def set_db(
        self,
        db,
    ) -> None:

        self.db = db

    def has_database(self) -> bool:

        return self.db is not None

    ####################################################################
    # Generic Query Helpers
    ####################################################################

    def _execute(
        self,
        sql: str,
        params: Optional[Dict[str, Any]] = None,
    ):

        if self.db is None:
            return None

        try:

            return self.db.execute(
                text(sql),
                params or {},
            )

        except SQLAlchemyError:

            logger.exception(
                "Database query failed."
            )

            return None

    def _fetch_all(
        self,
        sql: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:

        result = self._execute(
            sql,
            params,
        )

        if result is None:
            return []

        try:

            return [
                dict(row._mapping)
                for row in result.fetchall()
            ]

        except Exception:

            logger.exception(
                "Unable to fetch rows."
            )

            return []

    def _fetch_one(
        self,
        sql: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:

        result = self._execute(
            sql,
            params,
        )

        if result is None:
            return None

        try:

            row = result.fetchone()

            if row is None:
                return None

            return dict(
                row._mapping
            )

        except Exception:

            logger.exception(
                "Unable to fetch row."
            )

            return None

    ####################################################################
    # Table Inspection
    ####################################################################

    def table_exists(
        self,
        table: str,
    ) -> bool:

        if self.db is None:
            return False

        sql = """
        SELECT EXISTS (

            SELECT 1

            FROM information_schema.tables

            WHERE table_name = :table

        )
        """

        row = self._fetch_one(
            sql,
            {
                "table": table,
            },
        )

        if not row:
            return False

        return bool(
            list(row.values())[0]
        )

    ####################################################################
    # Generic Table Loader
    ####################################################################

    def _load_table_rows(
        self,
        *,
        table: str,
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        limit: int = 250,
        order_by_candidates=(
            "updated_at",
            "created_at",
            "filled_at",
            "executed_at",
            "closed_at",
            "opened_at",
            "id",
        ),
    ) -> List[Dict[str, Any]]:

        if self.db is None:

            return []

        if not self.table_exists(table):

            return []

        #
        # Determine ordering column.
        #

        order_column = "id"

        try:

            columns = self._fetch_all(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name=:table
                """,
                {
                    "table": table,
                },
            )

            names = {
                c["column_name"]
                for c in columns
            }

            for candidate in order_by_candidates:

                if candidate in names:

                    order_column = candidate

                    break

        except Exception:

            pass

        sql = f"""
        SELECT *
        FROM {table}
        WHERE
            (:account_id IS NULL OR account_id=:account_id)
        AND
            (:portfolio_id IS NULL OR portfolio_id=:portfolio_id)
        ORDER BY {order_column} DESC
        LIMIT :limit
        """

        return self._fetch_all(
            sql,
            {
                "account_id": account_id,
                "portfolio_id": portfolio_id,
                "limit": limit,
            },
        )
    ####################################################################
    # Execution History
    ####################################################################

    def load_execution_history(
        self,
        *,
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        limit: int = 250,
    ) -> List[Dict[str, Any]]:
        """
        Unified execution history.

        Preference:

            execution_events
            execution_orders
            forex_fills
            forex_executions
            forex_trade_orders
        """

        #
        # New institutional event stream
        #

        if self.table_exists(self.execution_events_table):

            rows = self._load_table_rows(
                table=self.execution_events_table,
                account_id=account_id,
                portfolio_id=portfolio_id,
                limit=limit,
                order_by_candidates=(
                    "event_time",
                    "created_at",
                    "timestamp",
                    "id",
                ),
            )

            if rows:
                return rows

        #
        # New execution orders
        #

        if self.table_exists(self.execution_orders_table):

            rows = self._load_table_rows(
                table=self.execution_orders_table,
                account_id=account_id,
                portfolio_id=portfolio_id,
                limit=limit,
                order_by_candidates=(
                    "filled_at",
                    "updated_at",
                    "created_at",
                    "id",
                ),
            )

            if rows:
                return rows

        #
        # Legacy fallback tables
        #

        legacy_tables = (

            self.fills_table,

            self.executions_table,

            self.trade_orders_table,

        )

        for table in legacy_tables:

            rows = self._load_table_rows(
                table=table,
                account_id=account_id,
                portfolio_id=portfolio_id,
                limit=limit,
            )

            if rows:
                return rows

        return []

    ####################################################################
    # Orders
    ####################################################################

    def load_orders(
        self,
        *,
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        include_cancelled: bool = True,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:

        rows: List[Dict[str, Any]] = []

        #
        # Institutional table
        #

        if self.table_exists(self.execution_orders_table):

            rows = self._load_table_rows(
                table=self.execution_orders_table,
                account_id=account_id,
                portfolio_id=portfolio_id,
                limit=limit,
                order_by_candidates=(
                    "updated_at",
                    "created_at",
                    "id",
                ),
            )

        #
        # Legacy fallback
        #

        elif self.table_exists(self.trade_orders_table):

            rows = self._load_table_rows(
                table=self.trade_orders_table,
                account_id=account_id,
                portfolio_id=portfolio_id,
                limit=limit,
            )

        if include_cancelled:

            return rows

        filtered = []

        for row in rows:

            status = str(
                row.get(
                    "status",
                    "",
                )
            ).upper()

            if status not in {

                "CANCELLED",

                "CANCELED",

                "REJECTED",

            }:

                filtered.append(row)

        return filtered

    ####################################################################
    # Open Positions
    ####################################################################

    def load_open_positions(
        self,
        *,
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:

        #
        # Institutional positions
        #

        if self.table_exists(self.execution_positions_table):

            rows = self._load_table_rows(
                table=self.execution_positions_table,
                account_id=account_id,
                portfolio_id=portfolio_id,
                limit=limit,
                order_by_candidates=(
                    "updated_at",
                    "opened_at",
                    "created_at",
                    "id",
                ),
            )

            if rows:

                open_rows = []

                for row in rows:

                    status = str(
                        row.get(
                            "status",
                            "OPEN",
                        )
                    ).upper()

                    if status in {

                        "OPEN",

                        "ACTIVE",

                    }:

                        open_rows.append(row)

                return open_rows

        #
        # Legacy positions
        #

        if self.table_exists(self.positions_table):

            rows = self._load_table_rows(
                table=self.positions_table,
                account_id=account_id,
                portfolio_id=portfolio_id,
                limit=limit,
            )

            open_rows = []

            for row in rows:

                quantity = float(
                    row.get(
                        "units",
                        row.get(
                            "quantity",
                            0,
                        ),
                    ) or 0
                )

                if quantity != 0:

                    open_rows.append(row)

            return open_rows

        return []

    ####################################################################
    # Closed Positions
    ####################################################################

    def load_closed_positions(
        self,
        *,
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:

        #
        # Institutional positions
        #

        if self.table_exists(self.execution_positions_table):

            rows = self._load_table_rows(
                table=self.execution_positions_table,
                account_id=account_id,
                portfolio_id=portfolio_id,
                limit=limit,
                order_by_candidates=(
                    "closed_at",
                    "updated_at",
                    "id",
                ),
            )

            closed = []

            for row in rows:

                status = str(
                    row.get(
                        "status",
                        "",
                    )
                ).upper()

                if status in {

                    "CLOSED",

                    "EXITED",

                    "FLAT",

                }:

                    closed.append(row)

            if closed:

                return closed

        #
        # Legacy closed trades
        #

        if self.table_exists(self.closed_positions_table):

            return self._load_table_rows(
                table=self.closed_positions_table,
                account_id=account_id,
                portfolio_id=portfolio_id,
                limit=limit,
                order_by_candidates=(
                    "closed_at",
                    "updated_at",
                    "id",
                ),
            )

        return []

    ####################################################################
    # Execution Events
    ####################################################################

    def load_execution_events(
        self,
        *,
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:

        rows = self.load_execution_history(
            account_id=account_id,
            portfolio_id=portfolio_id,
            limit=limit,
        )

        if event_type is None:

            return rows

        event_type = event_type.upper()

        filtered = []

        for row in rows:

            value = (

                row.get("event_type")

                or row.get("type")

                or row.get("status")

                or ""

            )

            if str(value).upper() == event_type:

                filtered.append(row)

        return filtered
    ####################################################################
    # Execution Statistics
    ####################################################################

    def load_execution_statistics(
        self,
        *,
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
    ) -> Dict[str, Any]:

        orders = self.load_orders(
            account_id=account_id,
            portfolio_id=portfolio_id,
            limit=100000,
        )

        open_positions = self.load_open_positions(
            account_id=account_id,
            portfolio_id=portfolio_id,
            limit=100000,
        )

        closed_positions = self.load_closed_positions(
            account_id=account_id,
            portfolio_id=portfolio_id,
            limit=100000,
        )

        total_orders = len(orders)

        filled = 0
        pending = 0
        cancelled = 0
        rejected = 0

        for order in orders:

            status = str(
                order.get(
                    "status",
                    "",
                )
            ).upper()

            if status in {"FILLED", "EXECUTED"}:
                filled += 1

            elif status in {"PENDING", "OPEN", "WORKING"}:
                pending += 1

            elif status in {"CANCELLED", "CANCELED"}:
                cancelled += 1

            elif status == "REJECTED":
                rejected += 1

        return {

            "total_orders": total_orders,

            "filled_orders": filled,

            "pending_orders": pending,

            "cancelled_orders": cancelled,

            "rejected_orders": rejected,

            "open_positions": len(open_positions),

            "closed_positions": len(closed_positions),

        }

    ####################################################################
    # Symbol Statistics
    ####################################################################

    def load_symbol_statistics(
        self,
        *,
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:

        rows = self.load_execution_history(
            account_id=account_id,
            portfolio_id=portfolio_id,
            limit=100000,
        )

        symbols: Dict[str, Dict[str, Any]] = {}

        for row in rows:

            symbol = (

                row.get("symbol")

                or row.get("pair")

                or "UNKNOWN"

            )

            if symbol not in symbols:

                symbols[symbol] = {

                    "symbol": symbol,

                    "executions": 0,

                    "buy_orders": 0,

                    "sell_orders": 0,

                    "volume": 0.0,

                }

            info = symbols[symbol]

            info["executions"] += 1

            qty = float(

                row.get(

                    "units",

                    row.get(

                        "quantity",

                        0,

                    ),

                ) or 0

            )

            info["volume"] += abs(qty)

            side = str(

                row.get(

                    "side",

                    "",

                )

            ).upper()

            if side == "BUY":

                info["buy_orders"] += 1

            elif side == "SELL":

                info["sell_orders"] += 1

        return sorted(

            symbols.values(),

            key=lambda x: x["executions"],

            reverse=True,

        )

    ####################################################################
    # Strategy Statistics
    ####################################################################

    def load_strategy_statistics(
        self,
        *,
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:

        rows = self.load_execution_history(
            account_id=account_id,
            portfolio_id=portfolio_id,
            limit=100000,
        )

        strategies: Dict[str, Dict[str, Any]] = {}

        for row in rows:

            strategy = (

                row.get("strategy")

                or row.get("strategy_name")

                or "Manual"

            )

            if strategy not in strategies:

                strategies[strategy] = {

                    "strategy": strategy,

                    "executions": 0,

                    "volume": 0.0,

                }

            stats = strategies[strategy]

            stats["executions"] += 1

            stats["volume"] += abs(

                float(

                    row.get(

                        "units",

                        row.get(

                            "quantity",

                            0,

                        ),

                    ) or 0

                )

            )

        return sorted(

            strategies.values(),

            key=lambda x: x["executions"],

            reverse=True,

        )

    ####################################################################
    # Daily Statistics
    ####################################################################

    def load_daily_statistics(
        self,
        *,
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:

        rows = self.load_execution_history(
            account_id=account_id,
            portfolio_id=portfolio_id,
            limit=100000,
        )

        days: Dict[str, Dict[str, Any]] = {}

        for row in rows:

            dt = (

                row.get("filled_at")

                or row.get("executed_at")

                or row.get("created_at")

                or row.get("timestamp")

            )

            if dt is None:
                continue

            day = str(dt)[:10]

            if day not in days:

                days[day] = {

                    "date": day,

                    "executions": 0,

                    "volume": 0.0,

                }

            info = days[day]

            info["executions"] += 1

            info["volume"] += abs(

                float(

                    row.get(

                        "units",

                        row.get(

                            "quantity",

                            0,

                        ),

                    ) or 0

                )

            )

        return sorted(

            days.values(),

            key=lambda x: x["date"],

        )

    ####################################################################
    # Execution Timeline
    ####################################################################

    def load_execution_timeline(
        self,
        *,
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:

        history = self.load_execution_history(
            account_id=account_id,
            portfolio_id=portfolio_id,
            limit=limit,
        )

        timeline = []

        for row in history:

            timeline.append({

                "timestamp": (

                    row.get("event_time")

                    or row.get("filled_at")

                    or row.get("executed_at")

                    or row.get("created_at")

                ),

                "symbol": (

                    row.get("symbol")

                    or row.get("pair")

                ),

                "event": (

                    row.get("event_type")

                    or row.get("status")

                ),

                "side": row.get("side"),

                "price": row.get("price"),

                "quantity": (

                    row.get("units")

                    or row.get("quantity")

                ),

                "order_id": row.get("order_id"),

                "position_id": row.get("position_id"),

            })

        return timeline
    ####################################################################
    # Performance Metrics
    ####################################################################

    def load_performance_metrics(
        self,
        *,
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
    ) -> Dict[str, Any]:

        closed_positions = self.load_closed_positions(
            account_id=account_id,
            portfolio_id=portfolio_id,
            limit=100000,
        )

        total_trades = len(closed_positions)

        winning_trades = 0
        losing_trades = 0

        gross_profit = 0.0
        gross_loss = 0.0

        largest_win = 0.0
        largest_loss = 0.0

        total_duration = 0.0
        duration_count = 0

        for trade in closed_positions:

            pnl = float(
                trade.get(
                    "realized_pnl",
                    trade.get(
                        "pnl",
                        trade.get(
                            "profit_loss",
                            0,
                        ),
                    ),
                )
                or 0
            )

            if pnl >= 0:

                winning_trades += 1
                gross_profit += pnl
                largest_win = max(
                    largest_win,
                    pnl,
                )

            else:

                losing_trades += 1
                gross_loss += abs(pnl)
                largest_loss = min(
                    largest_loss,
                    pnl,
                )

            opened = trade.get("opened_at")
            closed = trade.get("closed_at")

            try:

                if opened and closed:

                    duration = (
                        closed - opened
                    ).total_seconds()

                    total_duration += duration
                    duration_count += 1

            except Exception:

                pass

        win_rate = 0.0

        if total_trades:

            win_rate = (
                winning_trades
                / total_trades
            ) * 100.0

        profit_factor = None

        if gross_loss > 0:

            profit_factor = (
                gross_profit
                / gross_loss
            )

        avg_duration = None

        if duration_count:

            avg_duration = (
                total_duration
                / duration_count
            )

        return {

            "total_trades": total_trades,

            "winning_trades": winning_trades,

            "losing_trades": losing_trades,

            "win_rate": win_rate,

            "gross_profit": gross_profit,

            "gross_loss": gross_loss,

            "net_profit": (
                gross_profit
                - gross_loss
            ),

            "largest_win": largest_win,

            "largest_loss": largest_loss,

            "profit_factor": profit_factor,

            "average_trade_duration_seconds": avg_duration,

        }

    ####################################################################
    # Execution Quality
    ####################################################################

    def load_execution_quality(
        self,
        *,
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
    ) -> Dict[str, Any]:

        history = self.load_execution_history(
            account_id=account_id,
            portfolio_id=portfolio_id,
            limit=100000,
        )

        fills = 0

        slippage = []

        latency = []

        partial_fills = 0

        for row in history:

            status = str(
                row.get(
                    "status",
                    "",
                )
            ).upper()

            if status in {

                "FILLED",

                "EXECUTED",

            }:

                fills += 1

            expected = row.get(
                "expected_price"
            )

            actual = row.get(
                "execution_price",
                row.get(
                    "fill_price",
                    row.get(
                        "price",
                    ),
                ),
            )

            try:

                if expected is not None and actual is not None:

                    slippage.append(
                        float(actual)
                        - float(expected)
                    )

            except Exception:

                pass

            try:

                if (
                    row.get("submitted_at")
                    and row.get("filled_at")
                ):

                    latency.append(

                        (
                            row["filled_at"]
                            - row["submitted_at"]
                        ).total_seconds()

                    )

            except Exception:

                pass

            filled_qty = float(
                row.get(
                    "filled_quantity",
                    row.get(
                        "filled_units",
                        0,
                    ),
                )
                or 0
            )

            order_qty = float(
                row.get(
                    "quantity",
                    row.get(
                        "units",
                        filled_qty,
                    ),
                )
                or 0
            )

            if (

                order_qty > 0

                and filled_qty < order_qty

            ):

                partial_fills += 1

        avg_slippage = None

        if slippage:

            avg_slippage = (
                sum(slippage)
                / len(slippage)
            )

        avg_latency = None

        if latency:

            avg_latency = (
                sum(latency)
                / len(latency)
            )

        return {

            "fills": fills,

            "partial_fills": partial_fills,

            "average_slippage": avg_slippage,

            "average_latency_seconds": avg_latency,

            "fill_rate": (
                (
                    fills
                    / len(history)
                ) * 100.0
                if history
                else 0.0
            ),

        }

    ####################################################################
    # Portfolio Exposure
    ####################################################################

    def load_portfolio_exposure(
        self,
        *,
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:

        positions = self.load_open_positions(
            account_id=account_id,
            portfolio_id=portfolio_id,
            limit=100000,
        )

        exposure: Dict[str, Dict[str, Any]] = {}

        for row in positions:

            symbol = (

                row.get("symbol")

                or row.get("pair")

                or "UNKNOWN"

            )

            if symbol not in exposure:

                exposure[symbol] = {

                    "symbol": symbol,

                    "long_units": 0.0,

                    "short_units": 0.0,

                    "net_units": 0.0,

                }

            units = abs(

                float(

                    row.get(

                        "units",

                        row.get(

                            "quantity",

                            0,

                        ),

                    ) or 0

                )

            )

            side = str(
                row.get(
                    "side",
                    "",
                )
            ).upper()

            if side == "BUY":

                exposure[symbol][
                    "long_units"
                ] += units

                exposure[symbol][
                    "net_units"
                ] += units

            else:

                exposure[symbol][
                    "short_units"
                ] += units

                exposure[symbol][
                    "net_units"
                ] -= units

        return sorted(

            exposure.values(),

            key=lambda x: abs(
                x["net_units"]
            ),

            reverse=True,

        )

    ####################################################################
    # Dashboard Summary
    ####################################################################

    def load_dashboard_summary(
        self,
        *,
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
    ) -> Dict[str, Any]:

        return {

            "statistics":
                self.load_execution_statistics(
                    account_id=account_id,
                    portfolio_id=portfolio_id,
                ),

            "performance":
                self.load_performance_metrics(
                    account_id=account_id,
                    portfolio_id=portfolio_id,
                ),

            "quality":
                self.load_execution_quality(
                    account_id=account_id,
                    portfolio_id=portfolio_id,
                ),

            "exposure":
                self.load_portfolio_exposure(
                    account_id=account_id,
                    portfolio_id=portfolio_id,
                ),

            "timeline":
                self.load_execution_timeline(
                    account_id=account_id,
                    portfolio_id=portfolio_id,
                ),

        }

    ####################################################################
    # AI Execution Summary
    ####################################################################

    def load_ai_execution_summary(
            self,
            *,
            account_id: Optional[str] = None,
            portfolio_id: Optional[str] = None,
    ) -> Dict[str, Any]:

        performance = self.load_performance_metrics(
            account_id=account_id,
            portfolio_id=portfolio_id,
        )

        quality = self.load_execution_quality(
            account_id=account_id,
            portfolio_id=portfolio_id,
        )

        exposure = self.load_portfolio_exposure(
            account_id=account_id,
            portfolio_id=portfolio_id,
        )

        statistics = self.load_execution_statistics(
            account_id=account_id,
            portfolio_id=portfolio_id,
        )

        observations = []

        #
        # Win rate
        #

        win_rate = performance.get("win_rate", 0.0)

        if win_rate >= 70:
            observations.append(
                "Trading performance is excellent with a high win rate."
            )

        elif win_rate >= 55:
            observations.append(
                "Trading performance is healthy and consistent."
            )

        else:
            observations.append(
                "Win rate is below target. Review entry and exit quality."
            )

        #
        # Profit factor
        #

        pf = performance.get("profit_factor")

        if pf is not None:

            if pf >= 2.0:

                observations.append(
                    "Profit factor is institutional quality."
                )

            elif pf >= 1.3:

                observations.append(
                    "Profit factor is acceptable."
                )

            else:

                observations.append(
                    "Profit factor needs improvement."
                )

        #
        # Execution Quality
        #

        fill_rate = quality.get(
            "fill_rate",
            0,
        )

        if fill_rate >= 95:

            observations.append(
                "Execution fill quality is excellent."
            )

        elif fill_rate >= 80:

            observations.append(
                "Execution quality is acceptable."
            )

        else:

            observations.append(
                "Execution quality is below expectations."
            )

        #
        # Slippage
        #

        slippage = quality.get(
            "average_slippage"
        )

        if slippage is not None:

            if abs(slippage) <= 0.0001:

                observations.append(
                    "Very low average slippage."
                )

            else:

                observations.append(
                    "Average slippage should be monitored."
                )

        return {

            "headline":
                "Forex Execution Intelligence",

            "statistics":
                statistics,

            "performance":
                performance,

            "quality":
                quality,

            "exposure":
                exposure,

            "summary":
                observations,

        }

    ####################################################################
    # Health Check
    ####################################################################

    def repository_health(
            self,
    ) -> Dict[str, Any]:

        return {

            "database_connected":
                self.db is not None,

            "execution_events":
                self.table_exists(
                    self.execution_events_table
                ),

            "execution_orders":
                self.table_exists(
                    self.execution_orders_table
                ),

            "execution_positions":
                self.table_exists(
                    self.execution_positions_table
                ),

            "legacy_orders":
                self.table_exists(
                    self.trade_orders_table
                ),

            "legacy_positions":
                self.table_exists(
                    self.positions_table
                ),

            "legacy_closed":
                self.table_exists(
                    self.closed_positions_table
                ),

            "legacy_executions":
                self.table_exists(
                    self.executions_table
                ),

            "legacy_fills":
                self.table_exists(
                    self.fills_table
                ),

        }

    ####################################################################
    # Cache Management
    ####################################################################

    def clear_cache(
            self,
    ) -> None:

        logger.info(
            "ForexExecutionRepository cache cleared."
        )

        #
        # Reserved for future caching layer.
        #

        return

    ####################################################################
    # Refresh
    ####################################################################

    def refresh(
            self,
    ) -> None:

        self.clear_cache()

        logger.info(
            "ForexExecutionRepository refreshed."
        )

    ####################################################################
    # Repository Status
    ####################################################################

    def status(
            self,
    ) -> Dict[str, Any]:

        return {

            "repository":
                self.__class__.__name__,

            "connected":
                self.db is not None,

            "health":
                self.repository_health(),

        }

####################################################################
# Repository Singleton
####################################################################

_FOREX_EXECUTION_REPOSITORY: Optional[
    ForexExecutionRepository
] = None


def get_forex_execution_repository(
    db=None,
) -> ForexExecutionRepository:
    """
    Return the shared Forex execution repository.
    """

    global _FOREX_EXECUTION_REPOSITORY

    if _FOREX_EXECUTION_REPOSITORY is None:

        _FOREX_EXECUTION_REPOSITORY = (
            ForexExecutionRepository(
                db=db,
            )
        )

    elif db is not None:

        _FOREX_EXECUTION_REPOSITORY.set_db(
            db,
        )

    return _FOREX_EXECUTION_REPOSITORY