"""
===============================================================================
Sprint 27 - Phase 1B
Institutional Execution Statistics Engine
===============================================================================

Purpose
-------
Provides execution analytics for the Institutional Orders Dashboard.

This module performs analytics only.

No UI.
No Streamlit.
No database writes.

===============================================================================
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from statistics import mean
from typing import Any, Dict, List, Optional


@dataclass
class ExecutionStatistics:

    total_orders: int = 0
    open_orders: int = 0
    pending_orders: int = 0
    filled_orders: int = 0
    cancelled_orders: int = 0
    rejected_orders: int = 0
    partial_fills: int = 0

    fill_rate: float = 0.0
    cancel_rate: float = 0.0
    reject_rate: float = 0.0

    average_fill_price: float = 0.0
    average_fill_size: float = 0.0

    average_fill_time_ms: float = 0.0
    average_order_lifetime_ms: float = 0.0

    executed_volume: float = 0.0
    largest_order: float = 0.0

    average_slippage: float = 0.0

    buy_orders: int = 0
    sell_orders: int = 0

    market_orders: int = 0
    limit_orders: int = 0
    stop_orders: int = 0

    symbols_traded: int = 0


class ForexExecutionStatisticsEngine:

    """
    Institutional execution statistics engine.
    """

    # ------------------------------------------------------------------

    def analyze(
        self,
        *,
        open_orders: List[Dict[str, Any]],
        filled_orders: List[Dict[str, Any]],
        pending_orders: List[Dict[str, Any]],
        cancelled_orders: List[Dict[str, Any]],
        execution_history: List[Dict[str, Any]],
    ) -> Dict[str, Any]:

        stats = ExecutionStatistics()

        stats.open_orders = len(open_orders)
        stats.pending_orders = len(pending_orders)
        stats.filled_orders = len(filled_orders)
        stats.cancelled_orders = len(cancelled_orders)

        stats.total_orders = (
            stats.open_orders
            + stats.pending_orders
            + stats.filled_orders
            + stats.cancelled_orders
        )

        self._count_order_types(
            stats,
            filled_orders,
            open_orders,
            pending_orders,
        )

        self._calculate_execution_metrics(
            stats,
            filled_orders,
        )

        self._calculate_latency(
            stats,
            execution_history,
        )

        self._calculate_rates(
            stats,
        )

        return self._to_dict(stats)

    # ------------------------------------------------------------------

    def _count_order_types(
        self,
        stats: ExecutionStatistics,
        *groups,
    ):

        symbols = set()

        for orders in groups:

            for order in orders:

                side = str(
                    order.get("side", "")
                ).upper()

                if side == "BUY":
                    stats.buy_orders += 1

                elif side == "SELL":
                    stats.sell_orders += 1

                order_type = str(
                    order.get("order_type", "")
                ).upper()

                if order_type == "MARKET":
                    stats.market_orders += 1

                elif order_type == "LIMIT":
                    stats.limit_orders += 1

                elif order_type == "STOP":
                    stats.stop_orders += 1

                pair = order.get("pair")

                if pair:
                    symbols.add(pair)

        stats.symbols_traded = len(symbols)

    # ------------------------------------------------------------------

    def _calculate_execution_metrics(
        self,
        stats: ExecutionStatistics,
        filled_orders: List[Dict[str, Any]],
    ):

        prices = []
        quantities = []
        slippage = []

        largest = 0.0

        for order in filled_orders:

            qty = float(
                order.get(
                    "filled_qty",
                    order.get(
                        "quantity",
                        0,
                    ),
                )
            )

            largest = max(
                largest,
                qty,
            )

            quantities.append(qty)

            price = order.get(
                "avg_fill_price",
                order.get(
                    "price",
                    0,
                ),
            )

            try:
                prices.append(float(price))
            except Exception:
                pass

            try:

                requested = float(
                    order.get(
                        "requested_price",
                        price,
                    )
                )

                executed = float(price)

                slippage.append(
                    abs(executed - requested)
                )

            except Exception:

                pass

        stats.executed_volume = sum(quantities)
        stats.largest_order = largest

        if prices:
            stats.average_fill_price = mean(prices)

        if quantities:
            stats.average_fill_size = mean(quantities)

        if slippage:
            stats.average_slippage = mean(slippage)

    # ------------------------------------------------------------------

    def _calculate_latency(
        self,
        stats: ExecutionStatistics,
        history: List[Dict[str, Any]],
    ):

        latency = []

        for event in history:

            submitted = event.get("submitted_at")
            filled = event.get("filled_at")

            if not submitted or not filled:
                continue

            try:

                if isinstance(submitted, str):
                    submitted = datetime.fromisoformat(submitted)

                if isinstance(filled, str):
                    filled = datetime.fromisoformat(filled)

                latency.append(

                    (filled - submitted).total_seconds()

                    * 1000

                )

            except Exception:

                continue

        if latency:

            stats.average_fill_time_ms = mean(latency)
            stats.average_order_lifetime_ms = mean(latency)

    # ------------------------------------------------------------------

    def _calculate_rates(
        self,
        stats: ExecutionStatistics,
    ):

        if stats.total_orders == 0:
            return

        stats.fill_rate = (
            stats.filled_orders
            / stats.total_orders
        ) * 100

        stats.cancel_rate = (
            stats.cancelled_orders
            / stats.total_orders
        ) * 100

        stats.reject_rate = (
            stats.rejected_orders
            / stats.total_orders
        ) * 100

    # ------------------------------------------------------------------

    @staticmethod
    def _to_dict(
        stats: ExecutionStatistics,
    ) -> Dict[str, Any]:

        return {

            **stats.__dict__,

            "order_distribution": {

                "BUY": stats.buy_orders,
                "SELL": stats.sell_orders,

            },

            "order_types": {

                "MARKET": stats.market_orders,
                "LIMIT": stats.limit_orders,
                "STOP": stats.stop_orders,

            },

        }