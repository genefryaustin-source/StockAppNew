"""
===============================================================================
File: forex_execution_analytics_engine.py

Sprint 27 - Phase 1B
Institutional Forex Execution Analytics Engine

This engine sits above:

    forex_execution_statistics_engine.py
    forex_execution_quality_engine.py

It aggregates execution analytics into a single packet consumed by the
Trading Desk Orders dashboard.

This module intentionally contains NO Streamlit code.

===============================================================================
"""

from __future__ import annotations

import logging

from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from datetime import timezone

from typing import Any
from typing import Dict
from typing import Iterable
from typing import List
from typing import Optional

from modules.forex.forex_execution_statistics_engine import (
    ForexExecutionStatisticsEngine,
)

from modules.forex.forex_execution_quality_engine import (
    ForexExecutionQualityEngine,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Executive Summary
# =============================================================================

@dataclass
class ExecutionExecutiveSummary:

    total_orders: int = 0

    open_orders: int = 0

    filled_orders: int = 0

    pending_orders: int = 0

    cancelled_orders: int = 0

    execution_count: int = 0

    fill_rate: float = 0.0

    broker_score: float = 0.0

    execution_grade: str = "N/A"

    latency_ms: float = 0.0

    slippage: float = 0.0

    total_volume: float = 0.0

    execution_cost: float = 0.0

    generated_at: Optional[str] = None


# =============================================================================
# Dashboard Packet
# =============================================================================

@dataclass
class ExecutionAnalyticsPacket:

    executive_summary: Dict[str, Any] = field(default_factory=dict)

    statistics: Dict[str, Any] = field(default_factory=dict)

    quality: Dict[str, Any] = field(default_factory=dict)

    broker: Dict[str, Any] = field(default_factory=dict)

    distributions: Dict[str, Any] = field(default_factory=dict)

    timeline: List[Dict[str, Any]] = field(default_factory=list)

    dashboard: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Analytics Engine
# =============================================================================

class ForexExecutionAnalyticsEngine:

    """
    Master analytics engine.

    Aggregates

        • execution statistics
        • execution quality
        • dashboard KPIs
        • broker metrics
        • execution distributions
        • execution timeline

    into a single analytics packet.

    """

    # -------------------------------------------------------------------------
    # Constructor
    # -------------------------------------------------------------------------

    def __init__(self):

        self.statistics_engine = ForexExecutionStatisticsEngine()

        self.quality_engine = ForexExecutionQualityEngine()

    # -------------------------------------------------------------------------
    # Public Entry Point
    # -------------------------------------------------------------------------

    def build_execution_packet(

        self,

        *,

        open_orders: Optional[Iterable[Any]] = None,

        filled_orders: Optional[Iterable[Any]] = None,

        pending_orders: Optional[Iterable[Any]] = None,

        cancelled_orders: Optional[Iterable[Any]] = None,

        execution_history: Optional[Iterable[Any]] = None,

    ) -> Dict[str, Any]:

        """
        Main entry point.

        Returns one analytics packet used by the Orders dashboard.
        """

        open_orders = self._normalize(open_orders)

        filled_orders = self._normalize(filled_orders)

        pending_orders = self._normalize(pending_orders)

        cancelled_orders = self._normalize(cancelled_orders)

        execution_history = self._normalize(execution_history)

        # -------------------------------------------------------------
        # Statistics Engine
        # -------------------------------------------------------------

        statistics = self.statistics_engine.analyze(

            open_orders=open_orders,

            filled_orders=filled_orders,

            pending_orders=pending_orders,

            cancelled_orders=cancelled_orders,

            execution_history=execution_history,

        )

        # -------------------------------------------------------------
        # Quality Engine
        # -------------------------------------------------------------

        quality = self.quality_engine.analyze(

            filled_orders=filled_orders,

            execution_history=execution_history,

        )

        # -------------------------------------------------------------
        # Executive Summary
        # -------------------------------------------------------------

        executive_summary = self._build_executive_summary(

            statistics=statistics,

            quality=quality,

        )

        packet = ExecutionAnalyticsPacket(

            executive_summary=executive_summary,

            statistics=statistics,

            quality=quality,

            broker={},

            distributions={},

            timeline=[],

            dashboard={},

        )

        return {

            "executive_summary": packet.executive_summary,

            "statistics": packet.statistics,

            "quality": packet.quality,

            "broker": packet.broker,

            "distributions": packet.distributions,

            "timeline": packet.timeline,

            "dashboard": packet.dashboard,

        }

    # -------------------------------------------------------------------------
    # Executive Summary Builder
    # -------------------------------------------------------------------------

    def _build_executive_summary(

        self,

        *,

        statistics: Dict[str, Any],

        quality: Dict[str, Any],

    ) -> Dict[str, Any]:

        summary = ExecutionExecutiveSummary()

        summary.total_orders = statistics.get(

            "total_orders",

            0,

        )

        summary.open_orders = statistics.get(

            "open_orders",

            0,

        )

        summary.filled_orders = statistics.get(

            "filled_orders",

            0,

        )

        summary.pending_orders = statistics.get(

            "pending_orders",

            0,

        )

        summary.cancelled_orders = statistics.get(

            "cancelled_orders",

            0,

        )

        summary.execution_count = quality.get(

            "execution_count",

            0,

        )

        summary.fill_rate = statistics.get(

            "fill_rate",

            0.0,

        )

        summary.broker_score = quality.get(

            "broker_score",

            0.0,

        )

        summary.execution_grade = quality.get(

            "execution_grade",

            "N/A",

        )

        summary.latency_ms = quality.get(

            "average_latency_ms",

            0.0,

        )

        summary.slippage = quality.get(

            "average_slippage",

            0.0,

        )

        summary.total_volume = statistics.get(

            "total_volume",

            0.0,

        )

        summary.execution_cost = quality.get(

            "total_execution_cost",

            0.0,

        )

        summary.generated_at = datetime.now(

            timezone.utc,

        ).isoformat()

        return summary.__dict__

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    @staticmethod

    def _normalize(

        rows: Optional[Iterable[Any]],

    ) -> List[Any]:

        if rows is None:

            return []

        if isinstance(rows, list):

            return rows

        return list(rows)

    # -------------------------------------------------------------------------
    # Broker Analytics
    # -------------------------------------------------------------------------

    def _build_broker_summary(
        self,
        *,
        statistics: Dict[str, Any],
        quality: Dict[str, Any],
    ) -> Dict[str, Any]:

        return {

            "broker_score": quality.get(
                "broker_score",
                0.0,
            ),

            "execution_grade": quality.get(
                "execution_grade",
                "N/A",
            ),

            "latency_rating": quality.get(
                "latency_rating",
                "N/A",
            ),

            "slippage_rating": quality.get(
                "slippage_rating",
                "N/A",
            ),

            "cost_rating": quality.get(
                "cost_rating",
                "N/A",
            ),

            "average_latency_ms": quality.get(
                "average_latency_ms",
                0.0,
            ),

            "average_slippage": quality.get(
                "average_slippage",
                0.0,
            ),

            "average_execution_cost": quality.get(
                "average_execution_cost",
                0.0,
            ),

            "fill_rate": statistics.get(
                "fill_rate",
                0.0,
            ),

            "generated_at": datetime.now(
                timezone.utc,
            ).isoformat(),

        }

    # -------------------------------------------------------------------------
    # Distribution Builder
    # -------------------------------------------------------------------------

    def _build_distributions(
        self,
        *,
        open_orders: List[Any],
        filled_orders: List[Any],
        pending_orders: List[Any],
        cancelled_orders: List[Any],
    ) -> Dict[str, Any]:

        all_orders = (
            open_orders
            + filled_orders
            + pending_orders
            + cancelled_orders
        )

        return {

            "pair_distribution":
                self._pair_distribution(all_orders),

            "side_distribution":
                self._side_distribution(all_orders),

            "order_type_distribution":
                self._order_type_distribution(all_orders),

            "status_distribution":
                self._status_distribution(
                    open_orders,
                    filled_orders,
                    pending_orders,
                    cancelled_orders,
                ),

        }

    # -------------------------------------------------------------------------
    # Pair Distribution
    # -------------------------------------------------------------------------

    def _pair_distribution(
        self,
        rows: List[Any],
    ) -> List[Dict[str, Any]]:

        counts = {}

        for row in rows:

            pair = self._field(
                row,
                "pair",
                "symbol",
            )

            if not pair:

                continue

            counts[pair] = counts.get(pair, 0) + 1

        return [

            {

                "pair": pair,

                "orders": total,

            }

            for pair, total in sorted(
                counts.items(),
            )

        ]

    # -------------------------------------------------------------------------
    # Side Distribution
    # -------------------------------------------------------------------------

    def _side_distribution(
        self,
        rows: List[Any],
    ) -> List[Dict[str, Any]]:

        counts = {

            "BUY": 0,

            "SELL": 0,

        }

        for row in rows:

            side = str(

                self._field(
                    row,
                    "side",
                )

            ).upper()

            if side in counts:

                counts[side] += 1

        return [

            {

                "side": side,

                "orders": total,

            }

            for side, total in counts.items()

        ]

    # -------------------------------------------------------------------------
    # Order Type Distribution
    # -------------------------------------------------------------------------

    def _order_type_distribution(
        self,
        rows: List[Any],
    ) -> List[Dict[str, Any]]:

        counts = {}

        for row in rows:

            order_type = str(

                self._field(
                    row,
                    "order_type",
                    "type",
                )

            ).upper()

            if not order_type:

                continue

            counts[order_type] = (

                counts.get(order_type, 0)

                + 1

            )

        return [

            {

                "order_type": k,

                "count": v,

            }

            for k, v in sorted(
                counts.items(),
            )

        ]

    # -------------------------------------------------------------------------
    # Status Distribution
    # -------------------------------------------------------------------------

    def _status_distribution(
        self,
        open_orders,
        filled_orders,
        pending_orders,
        cancelled_orders,
    ):

        return [

            {

                "status": "OPEN",

                "orders": len(open_orders),

            },

            {

                "status": "FILLED",

                "orders": len(filled_orders),

            },

            {

                "status": "PENDING",

                "orders": len(pending_orders),

            },

            {

                "status": "CANCELLED",

                "orders": len(cancelled_orders),

            },

        ]

    # -------------------------------------------------------------------------
    # Execution Timeline
    # -------------------------------------------------------------------------

    def _build_timeline(
        self,
        rows: List[Any],
    ) -> List[Dict[str, Any]]:

        timeline = []

        for row in rows:

            timeline.append(

                {

                    "pair": self._field(
                        row,
                        "pair",
                        "symbol",
                    ),

                    "side": self._field(
                        row,
                        "side",
                    ),

                    "order_type": self._field(
                        row,
                        "order_type",
                        "type",
                    ),

                    "quantity": self._field(
                        row,
                        "quantity",
                        "units",
                    ),

                    "price": self._field(
                        row,
                        "price",
                        "fill_price",
                        "avg_fill_price",
                    ),

                    "submitted_at": self._field(
                        row,
                        "submitted_at",
                        "created_at",
                    ),

                    "filled_at": self._field(
                        row,
                        "filled_at",
                        "executed_at",
                    ),

                    "broker_order_id": self._field(
                        row,
                        "broker_order_id",
                    ),

                }

            )

        timeline.sort(

            key=lambda x:

                x.get("filled_at")

                or ""

        )

        return timeline

    # -------------------------------------------------------------------------
    # Safe Field Access
    # -------------------------------------------------------------------------

    @staticmethod
    def _field(
        row,
        *names,
    ):

        if row is None:

            return None

        if hasattr(
            row,
            "to_dict",
        ):

            row = row.to_dict()

        if isinstance(
            row,
            dict,
        ):

            for name in names:

                value = row.get(name)

                if value is not None:

                    return value

        else:

            for name in names:

                if hasattr(
                    row,
                    name,
                ):

                    value = getattr(
                        row,
                        name,
                    )

                    if value is not None:

                        return value

        return None

    # -------------------------------------------------------------------------
    # Build Dashboard Packet
    # -------------------------------------------------------------------------

    def build_execution_packet(
            self,
            *,
            account_id: Optional[str] = None,
            portfolio_id: Optional[str] = None,
    ) -> Dict[str, Any]:

        statistics = self.statistics_engine.build_statistics(
            account_id=account_id,
            portfolio_id=portfolio_id,
        )

        quality = self.quality_engine.build_quality_report(
            account_id=account_id,
            portfolio_id=portfolio_id,
        )

        history = self.repository.load_execution_history(
            account_id=account_id,
            portfolio_id=portfolio_id,
            limit=500,
        )

        open_orders = self.repository.load_open_orders(
            account_id=account_id,
            portfolio_id=portfolio_id,
        )

        filled_orders = self.repository.load_filled_orders(
            account_id=account_id,
            portfolio_id=portfolio_id,
        )

        pending_orders = self.repository.load_pending_orders(
            account_id=account_id,
            portfolio_id=portfolio_id,
        )

        cancelled_orders = self.repository.load_cancelled_orders(
            account_id=account_id,
            portfolio_id=portfolio_id,
        )

        distributions = self._build_distributions(
            open_orders=open_orders,
            filled_orders=filled_orders,
            pending_orders=pending_orders,
            cancelled_orders=cancelled_orders,
        )

        broker = self._build_broker_summary(
            statistics=statistics,
            quality=quality,
        )

        timeline = self._build_timeline(history)

        executive = self._build_executive_summary(
            statistics=statistics,
            quality=quality,
            broker=broker,
        )

        charts = self._build_chart_packet(
            distributions=distributions,
        )

        return {

            "executive_summary": executive,

            "statistics": statistics,

            "quality": quality,

            "broker": broker,

            "charts": charts,

            "distributions": distributions,

            "timeline": timeline,

            "recent_executions": history[:50],

            "open_orders": open_orders,

            "filled_orders": filled_orders,

            "pending_orders": pending_orders,

            "cancelled_orders": cancelled_orders,

            "generated_at": datetime.now(
                timezone.utc,
            ).isoformat(),

        }

    # -------------------------------------------------------------------------
    # Executive Summary
    # -------------------------------------------------------------------------

    def _build_executive_summary(
            self,
            *,
            statistics,
            quality,
            broker,
    ):

        score = broker.get(
            "broker_score",
            0.0,
        )

        if score >= 95:

            rating = "Institutional"

        elif score >= 85:

            rating = "Excellent"

        elif score >= 75:

            rating = "Good"

        elif score >= 60:

            rating = "Fair"

        else:

            rating = "Poor"

        return {

            "execution_rating": rating,

            "broker_score": score,

            "fill_rate": statistics.get(
                "fill_rate",
                0.0,
            ),

            "average_latency_ms": quality.get(
                "average_latency_ms",
                0.0,
            ),

            "average_slippage": quality.get(
                "average_slippage",
                0.0,
            ),

            "reject_rate": statistics.get(
                "reject_rate",
                0.0,
            ),

            "execution_grade": quality.get(
                "execution_grade",
                "N/A",
            ),

        }

    # -------------------------------------------------------------------------
    # Chart Packet
    # -------------------------------------------------------------------------

    def _build_chart_packet(
            self,
            *,
            distributions,
    ):

        return {

            "pair_chart":
                distributions.get(
                    "pair_distribution",
                    [],
                ),

            "side_chart":
                distributions.get(
                    "side_distribution",
                    [],
                ),

            "order_type_chart":
                distributions.get(
                    "order_type_distribution",
                    [],
                ),

            "status_chart":
                distributions.get(
                    "status_distribution",
                    [],
                ),

        }

    # -------------------------------------------------------------------------
    # Convenience API
    # -------------------------------------------------------------------------

    def get_dashboard_data(
            self,
            *,
            account_id: Optional[str] = None,
            portfolio_id: Optional[str] = None,
    ) -> Dict[str, Any]:

        return self.build_execution_packet(
            account_id=account_id,
            portfolio_id=portfolio_id,
        )

    # =============================================================================
    # Singleton
    # =============================================================================

    _INSTANCE = None

    def get_forex_execution_analytics_engine(
            db=None,
    ):

        global _INSTANCE

        if (
                _INSTANCE is None
                or getattr(
            _INSTANCE,
            "db",
            None,
        ) is not db
        ):
            _INSTANCE = ForexExecutionAnalyticsEngine(
                db=db,
            )

        return _INSTANCE

    # -------------------------------------------------------------------------
    # Execution KPIs
    # -------------------------------------------------------------------------

    def execution_kpis(
        self,
        *,
        account_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
    ) -> Dict[str, Any]:

        packet = self.build_execution_packet(
            account_id=account_id,
            portfolio_id=portfolio_id,
        )

        statistics = packet["statistics"]
        quality = packet["quality"]

        return {

            "orders": statistics.get(
                "total_orders",
                0,
            ),

            "executions": quality.get(
                "execution_count",
                0,
            ),

            "fill_rate": statistics.get(
                "fill_rate",
                0.0,
            ),

            "reject_rate": statistics.get(
                "reject_rate",
                0.0,
            ),

            "latency_ms": quality.get(
                "average_latency_ms",
                0.0,
            ),

            "slippage": quality.get(
                "average_slippage",
                0.0,
            ),

            "broker_score": quality.get(
                "broker_score",
                0.0,
            ),

            "grade": quality.get(
                "execution_grade",
                "N/A",
            ),

        }

    # -------------------------------------------------------------------------
    # Dashboard Cards
    # -------------------------------------------------------------------------

    def dashboard_cards(
        self,
        *,
        account_id=None,
        portfolio_id=None,
    ):

        kpis = self.execution_kpis(
            account_id=account_id,
            portfolio_id=portfolio_id,
        )

        return [

            {

                "title": "Orders",

                "value": kpis["orders"],

            },

            {

                "title": "Executions",

                "value": kpis["executions"],

            },

            {

                "title": "Fill Rate",

                "value": f"{kpis['fill_rate']:.1f}%",

            },

            {

                "title": "Reject Rate",

                "value": f"{kpis['reject_rate']:.1f}%",

            },

            {

                "title": "Latency",

                "value": f"{kpis['latency_ms']:.0f} ms",

            },

            {

                "title": "Slippage",

                "value": f"{kpis['slippage']:.4f}",

            },

            {

                "title": "Broker Score",

                "value": f"{kpis['broker_score']:.1f}",

            },

            {

                "title": "Execution Grade",

                "value": kpis["grade"],

            },

        ]

    # -------------------------------------------------------------------------
    # Execution Health
    # -------------------------------------------------------------------------

    def execution_health(
        self,
        *,
        account_id=None,
        portfolio_id=None,
    ):

        packet = self.build_execution_packet(

            account_id=account_id,

            portfolio_id=portfolio_id,

        )

        quality = packet["quality"]

        score = float(

            quality.get(

                "broker_score",

                0,

            )

        )

        if score >= 95:

            status = "GREEN"

        elif score >= 80:

            status = "YELLOW"

        else:

            status = "RED"

        return {

            "status": status,

            "score": score,

            "grade": quality.get(

                "execution_grade",

                "N/A",

            ),

            "latency_ms": quality.get(

                "average_latency_ms",

                0,

            ),

            "slippage": quality.get(

                "average_slippage",

                0,

            ),

        }

    def build_execution_health(
            self,
            statistics: dict,
            quality: dict,
            broker: dict,
    ) -> dict:
        """
        Build an institutional execution health score.

        Returns
        -------
        {
            overall_score,
            grade,
            status,
            fill_rate_score,
            latency_score,
            slippage_score,
            broker_score,
        }
        """

        statistics = statistics or {}
        quality = quality or {}
        broker = broker or {}

        # ----------------------------------------------------------
        # Raw Metrics
        # ----------------------------------------------------------

        fill_rate = float(
            statistics.get(
                "fill_rate",
                0.0,
            )
        )

        latency = float(
            statistics.get(
                "latency_ms",
                quality.get(
                    "latency_ms",
                    999.0,
                ),
            )
        )

        slippage = abs(
            float(
                quality.get(
                    "avg_slippage",
                    quality.get(
                        "slippage",
                        0.0,
                    ),
                )
            )
        )

        reject_rate = float(
            statistics.get(
                "reject_rate",
                quality.get(
                    "reject_rate",
                    0.0,
                ),
            )
        )

        # ----------------------------------------------------------
        # Fill Rate Score
        # ----------------------------------------------------------

        if fill_rate >= 99:
            fill_rate_score = 100
        elif fill_rate >= 98:
            fill_rate_score = 95
        elif fill_rate >= 95:
            fill_rate_score = 90
        elif fill_rate >= 90:
            fill_rate_score = 80
        else:
            fill_rate_score = 60

        # ----------------------------------------------------------
        # Latency Score
        # ----------------------------------------------------------

        if latency <= 25:
            latency_score = 100
        elif latency <= 50:
            latency_score = 95
        elif latency <= 100:
            latency_score = 90
        elif latency <= 250:
            latency_score = 75
        else:
            latency_score = 50

        # ----------------------------------------------------------
        # Slippage Score
        # ----------------------------------------------------------

        if slippage <= 0.05:
            slippage_score = 100
        elif slippage <= 0.10:
            slippage_score = 95
        elif slippage <= 0.25:
            slippage_score = 90
        elif slippage <= 0.50:
            slippage_score = 75
        else:
            slippage_score = 50

        # ----------------------------------------------------------
        # Broker Score
        # ----------------------------------------------------------

        if reject_rate <= 0:
            broker_score = 100
        elif reject_rate <= 0.5:
            broker_score = 95
        elif reject_rate <= 1.0:
            broker_score = 90
        elif reject_rate <= 2.0:
            broker_score = 80
        else:
            broker_score = 60

        # ----------------------------------------------------------
        # Overall Score
        # ----------------------------------------------------------

        overall_score = round(
            (
                    fill_rate_score
                    + latency_score
                    + slippage_score
                    + broker_score
            ) / 4,
            1,
        )

        # ----------------------------------------------------------
        # Grade
        # ----------------------------------------------------------

        if overall_score >= 97:
            grade = "A+"
        elif overall_score >= 93:
            grade = "A"
        elif overall_score >= 90:
            grade = "A-"
        elif overall_score >= 85:
            grade = "B+"
        elif overall_score >= 80:
            grade = "B"
        elif overall_score >= 75:
            grade = "C"
        elif overall_score >= 65:
            grade = "D"
        else:
            grade = "F"

        # ----------------------------------------------------------
        # Status
        # ----------------------------------------------------------

        if overall_score >= 95:
            status = "Excellent"
        elif overall_score >= 90:
            status = "Very Good"
        elif overall_score >= 80:
            status = "Good"
        elif overall_score >= 70:
            status = "Fair"
        else:
            status = "Needs Attention"

        return {

            "overall_score": overall_score,

            "grade": grade,

            "status": status,

            "fill_rate_score": fill_rate_score,

            "latency_score": latency_score,

            "slippage_score": slippage_score,

            "broker_score": broker_score,

            # Raw metrics retained for drill-down
            "fill_rate": fill_rate,

            "latency_ms": latency,

            "avg_slippage": slippage,

            "reject_rate": reject_rate,

        }

    # ==========================================================
    # Execution Intelligence
    # ==========================================================

    def build_execution_intelligence(
            self,
            statistics: dict,
            quality: dict,
            broker: dict,
            execution_health: dict,
    ) -> dict:
        """
        Build a deterministic institutional execution-intelligence packet.

        This method does not call an AI model. It interprets the execution
        statistics, execution quality, broker metrics, and health score using
        explicit rules so the result can be consumed consistently by:

        - Trading Desk
        - Executive Dashboard
        - Broker Analytics
        - Operations Center
        - Future AI narrative generation

        Parameters
        ----------
        statistics:
            Output from ForexExecutionStatisticsEngine.

        quality:
            Output from ForexExecutionQualityEngine.

        broker:
            Broker analytics produced by ForexExecutionAnalyticsEngine.

        execution_health:
            Output from build_execution_health().

        Returns
        -------
        dict
            Institutional execution intelligence packet.
        """

        statistics = statistics or {}
        quality = quality or {}
        broker = broker or {}
        execution_health = execution_health or {}

        # ----------------------------------------------------------
        # Safe helpers
        # ----------------------------------------------------------

        def _safe_float(
                value,
                default: float = 0.0,
        ) -> float:
            try:
                if value is None or value == "":
                    return default

                number = float(value)

                if number != number:
                    return default

                if number in (
                        float("inf"),
                        float("-inf"),
                ):
                    return default

                return number

            except Exception:
                return default

        def _safe_int(
                value,
                default: int = 0,
        ) -> int:
            try:
                return int(
                    float(
                        value
                    )
                )
            except Exception:
                return default

        # ----------------------------------------------------------
        # Resolve raw execution metrics
        # ----------------------------------------------------------

        total_orders = _safe_int(
            statistics.get(
                "total_orders",
                0,
            )
        )

        filled_orders = _safe_int(
            statistics.get(
                "filled_orders",
                0,
            )
        )

        open_orders = _safe_int(
            statistics.get(
                "open_orders",
                0,
            )
        )

        pending_orders = _safe_int(
            statistics.get(
                "pending_orders",
                0,
            )
        )

        cancelled_orders = _safe_int(
            statistics.get(
                "cancelled_orders",
                0,
            )
        )

        rejected_orders = _safe_int(
            statistics.get(
                "rejected_orders",
                0,
            )
        )

        partial_fills = _safe_int(
            statistics.get(
                "partial_fills",
                0,
            )
        )

        fill_rate = _safe_float(
            statistics.get(
                "fill_rate",
                0.0,
            )
        )

        cancel_rate = _safe_float(
            statistics.get(
                "cancel_rate",
                0.0,
            )
        )

        reject_rate = _safe_float(
            statistics.get(
                "reject_rate",
                0.0,
            )
        )

        executed_volume = _safe_float(
            statistics.get(
                "executed_volume",
                statistics.get(
                    "total_volume",
                    0.0,
                ),
            )
        )

        average_fill_size = _safe_float(
            statistics.get(
                "average_fill_size",
                0.0,
            )
        )

        average_fill_price = _safe_float(
            statistics.get(
                "average_fill_price",
                0.0,
            )
        )

        average_fill_time_ms = _safe_float(
            statistics.get(
                "average_fill_time_ms",
                statistics.get(
                    "latency_ms",
                    0.0,
                ),
            )
        )

        # ----------------------------------------------------------
        # Resolve execution-quality metrics
        # ----------------------------------------------------------

        average_latency_ms = _safe_float(
            quality.get(
                "average_latency_ms",
                quality.get(
                    "latency_ms",
                    average_fill_time_ms,
                ),
            )
        )

        median_latency_ms = _safe_float(
            quality.get(
                "median_latency_ms",
                0.0,
            )
        )

        p95_latency_ms = _safe_float(
            quality.get(
                "p95_latency_ms",
                0.0,
            )
        )

        average_slippage = _safe_float(
            quality.get(
                "average_slippage",
                quality.get(
                    "avg_slippage",
                    quality.get(
                        "slippage",
                        0.0,
                    ),
                ),
            )
        )

        average_absolute_slippage = abs(
            _safe_float(
                quality.get(
                    "average_absolute_slippage",
                    average_slippage,
                )
            )
        )

        average_spread = _safe_float(
            quality.get(
                "average_spread",
                0.0,
            )
        )

        total_commission = _safe_float(
            quality.get(
                "total_commission",
                0.0,
            )
        )

        average_commission = _safe_float(
            quality.get(
                "average_commission",
                0.0,
            )
        )

        total_execution_cost = _safe_float(
            quality.get(
                "total_execution_cost",
                0.0,
            )
        )

        average_execution_cost = _safe_float(
            quality.get(
                "average_execution_cost",
                0.0,
            )
        )

        favorable_fill_rate = _safe_float(
            quality.get(
                "favorable_fill_rate",
                quality.get(
                    "quality_breakdown",
                    {},
                ).get(
                    "favorable_fill_rate",
                    0.0,
                )
                if isinstance(
                    quality.get(
                        "quality_breakdown",
                        {},
                    ),
                    dict,
                )
                else 0.0,
            )
        )

        adverse_fill_rate = _safe_float(
            quality.get(
                "adverse_fill_rate",
                quality.get(
                    "quality_breakdown",
                    {},
                ).get(
                    "adverse_fill_rate",
                    0.0,
                )
                if isinstance(
                    quality.get(
                        "quality_breakdown",
                        {},
                    ),
                    dict,
                )
                else 0.0,
            )
        )

        # ----------------------------------------------------------
        # Resolve broker and health metrics
        # ----------------------------------------------------------

        overall_score = _safe_float(
            execution_health.get(
                "overall_score",
                0.0,
            )
        )

        execution_grade = str(
            execution_health.get(
                "grade",
                quality.get(
                    "execution_grade",
                    broker.get(
                        "execution_grade",
                        "N/A",
                    ),
                ),
            )
            or "N/A"
        )

        execution_status = str(
            execution_health.get(
                "status",
                "Unknown",
            )
            or "Unknown"
        )

        broker_score = _safe_float(
            execution_health.get(
                "broker_score",
                broker.get(
                    "broker_score",
                    quality.get(
                        "broker_score",
                        0.0,
                    ),
                ),
            )
        )

        latency_rating = str(
            quality.get(
                "latency_rating",
                broker.get(
                    "latency_rating",
                    "N/A",
                ),
            )
            or "N/A"
        )

        slippage_rating = str(
            quality.get(
                "slippage_rating",
                broker.get(
                    "slippage_rating",
                    "N/A",
                ),
            )
            or "N/A"
        )

        cost_rating = str(
            quality.get(
                "cost_rating",
                broker.get(
                    "cost_rating",
                    "N/A",
                ),
            )
            or "N/A"
        )

        # ----------------------------------------------------------
        # Broker analysis
        # ----------------------------------------------------------

        broker_analysis = {
            "broker_score": round(
                broker_score,
                2,
            ),
            "execution_grade": execution_grade,
            "fill_rate": round(
                fill_rate,
                2,
            ),
            "reject_rate": round(
                reject_rate,
                2,
            ),
            "cancel_rate": round(
                cancel_rate,
                2,
            ),
            "average_latency_ms": round(
                average_latency_ms,
                2,
            ),
            "median_latency_ms": round(
                median_latency_ms,
                2,
            ),
            "p95_latency_ms": round(
                p95_latency_ms,
                2,
            ),
            "average_slippage": average_slippage,
            "average_absolute_slippage": average_absolute_slippage,
            "average_spread": average_spread,
            "latency_rating": latency_rating,
            "slippage_rating": slippage_rating,
            "cost_rating": cost_rating,
            "broker_name": broker.get(
                "name",
                broker.get(
                    "broker",
                    "Paper",
                ),
            ),
        }

        # ----------------------------------------------------------
        # Execution analysis
        # ----------------------------------------------------------

        execution_analysis = {
            "overall_score": round(
                overall_score,
                2,
            ),
            "grade": execution_grade,
            "status": execution_status,
            "total_orders": total_orders,
            "filled_orders": filled_orders,
            "open_orders": open_orders,
            "pending_orders": pending_orders,
            "cancelled_orders": cancelled_orders,
            "rejected_orders": rejected_orders,
            "partial_fills": partial_fills,
            "executed_volume": round(
                executed_volume,
                2,
            ),
            "average_fill_size": round(
                average_fill_size,
                2,
            ),
            "average_fill_price": average_fill_price,
            "average_fill_time_ms": round(
                average_fill_time_ms,
                2,
            ),
            "favorable_fill_rate": round(
                favorable_fill_rate,
                2,
            ),
            "adverse_fill_rate": round(
                adverse_fill_rate,
                2,
            ),
        }

        # ----------------------------------------------------------
        # Cost analysis
        # ----------------------------------------------------------

        cost_analysis = {
            "total_commission": round(
                total_commission,
                6,
            ),
            "average_commission": round(
                average_commission,
                6,
            ),
            "total_execution_cost": round(
                total_execution_cost,
                6,
            ),
            "average_execution_cost": round(
                average_execution_cost,
                6,
            ),
            "average_spread": average_spread,
            "average_absolute_slippage": average_absolute_slippage,
            "cost_rating": cost_rating,
        }

        # ----------------------------------------------------------
        # Risk analysis
        # ----------------------------------------------------------

        risk_level = "LOW"

        if (
                overall_score < 70
                or reject_rate > 2.0
                or average_latency_ms > 500
                or average_absolute_slippage > 0.001
        ):
            risk_level = "HIGH"

        elif (
                overall_score < 85
                or reject_rate > 1.0
                or average_latency_ms > 250
                or average_absolute_slippage > 0.0005
        ):
            risk_level = "MODERATE"

        risk_analysis = {
            "risk_level": risk_level,
            "execution_status": execution_status,
            "reject_rate": round(
                reject_rate,
                2,
            ),
            "cancel_rate": round(
                cancel_rate,
                2,
            ),
            "average_latency_ms": round(
                average_latency_ms,
                2,
            ),
            "p95_latency_ms": round(
                p95_latency_ms,
                2,
            ),
            "average_absolute_slippage": average_absolute_slippage,
            "adverse_fill_rate": round(
                adverse_fill_rate,
                2,
            ),
            "open_order_count": open_orders,
            "pending_order_count": pending_orders,
        }

        # ----------------------------------------------------------
        # Recommendations
        # ----------------------------------------------------------

        recommendations = []

        if total_orders == 0:
            recommendations.append(
                "No execution activity is available yet. Submit or import orders "
                "before evaluating broker and execution performance."
            )

        if fill_rate < 95 and total_orders > 0:
            recommendations.append(
                "Fill rate is below the 95% institutional target. Review order "
                "types, liquidity conditions, and broker routing behavior."
            )

        elif fill_rate >= 99 and total_orders > 0:
            recommendations.append(
                "Fill rate is excellent and currently meets institutional standards."
            )

        if reject_rate > 2:
            recommendations.append(
                "Broker reject rate is elevated. Review validation failures, "
                "margin availability, order sizing, and unsupported order types."
            )

        elif reject_rate > 1:
            recommendations.append(
                "Reject rate is above the preferred range and should be monitored."
            )

        if cancel_rate > 15:
            recommendations.append(
                "Cancellation activity is elevated. Review stale orders and "
                "order-lifetime settings."
            )

        if average_latency_ms > 500:
            recommendations.append(
                "Execution latency is materially elevated. Investigate broker "
                "connectivity, routing delays, and provider response times."
            )

        elif average_latency_ms > 250:
            recommendations.append(
                "Execution latency is above target. Monitor broker and network "
                "performance."
            )

        elif (
                average_latency_ms > 0
                and average_latency_ms <= 100
        ):
            recommendations.append(
                "Execution latency is operating within a strong institutional range."
            )

        if average_absolute_slippage > 0.001:
            recommendations.append(
                "Slippage is critically high. Reduce ticket size, avoid thin "
                "liquidity periods, and review execution routing."
            )

        elif average_absolute_slippage > 0.0005:
            recommendations.append(
                "Slippage is elevated. Consider smaller order slices or limit-order "
                "execution."
            )

        elif (
                average_absolute_slippage > 0
                and average_absolute_slippage <= 0.0002
        ):
            recommendations.append(
                "Average slippage remains within acceptable execution thresholds."
            )

        if adverse_fill_rate > 60:
            recommendations.append(
                "A majority of classified fills are adverse. Review requested-price "
                "benchmarks and broker execution quality."
            )

        if pending_orders > 0:
            recommendations.append(
                f"{pending_orders} pending order(s) require monitoring for stale "
                "pricing or missed trigger conditions."
            )

        if open_orders > 10:
            recommendations.append(
                "Open-order count is elevated. Review concentration, expiry, and "
                "cancellation controls."
            )

        if total_execution_cost > 0 and executed_volume > 0:
            cost_per_unit = (
                    total_execution_cost
                    / executed_volume
            )

            if cost_per_unit > 0.001:
                recommendations.append(
                    "Execution cost per unit is elevated relative to traded volume."
                )

        if overall_score >= 95 and total_orders > 0:
            recommendations.append(
                "Overall execution health is excellent. Maintain current controls "
                "and continue monitoring for deterioration."
            )

        if not recommendations:
            recommendations.append(
                "Execution performance is stable with no immediate corrective "
                "actions required."
            )

        # ----------------------------------------------------------
        # Alerts
        # ----------------------------------------------------------

        alerts = []

        if reject_rate > 2:
            alerts.append({
                "severity": "CRITICAL",
                "code": "HIGH_REJECT_RATE",
                "message": (
                    "Broker reject rate exceeds the 2% institutional threshold."
                ),
                "value": round(
                    reject_rate,
                    2,
                ),
            })

        if average_latency_ms > 500:
            alerts.append({
                "severity": "CRITICAL",
                "code": "HIGH_EXECUTION_LATENCY",
                "message": (
                    "Average execution latency exceeds 500 milliseconds."
                ),
                "value": round(
                    average_latency_ms,
                    2,
                ),
            })

        elif average_latency_ms > 250:
            alerts.append({
                "severity": "WARNING",
                "code": "ELEVATED_EXECUTION_LATENCY",
                "message": (
                    "Average execution latency exceeds the preferred target."
                ),
                "value": round(
                    average_latency_ms,
                    2,
                ),
            })

        if average_absolute_slippage > 0.001:
            alerts.append({
                "severity": "CRITICAL",
                "code": "CRITICAL_SLIPPAGE",
                "message": (
                    "Average absolute slippage exceeds the critical threshold."
                ),
                "value": average_absolute_slippage,
            })

        elif average_absolute_slippage > 0.0005:
            alerts.append({
                "severity": "WARNING",
                "code": "ELEVATED_SLIPPAGE",
                "message": (
                    "Average absolute slippage is above the preferred threshold."
                ),
                "value": average_absolute_slippage,
            })

        if fill_rate < 90 and total_orders > 0:
            alerts.append({
                "severity": "CRITICAL",
                "code": "LOW_FILL_RATE",
                "message": (
                    "Fill rate has fallen below 90%."
                ),
                "value": round(
                    fill_rate,
                    2,
                ),
            })

        elif fill_rate < 95 and total_orders > 0:
            alerts.append({
                "severity": "WARNING",
                "code": "BELOW_TARGET_FILL_RATE",
                "message": (
                    "Fill rate is below the 95% institutional target."
                ),
                "value": round(
                    fill_rate,
                    2,
                ),
            })

        if pending_orders > 5:
            alerts.append({
                "severity": "WARNING",
                "code": "PENDING_ORDER_BUILDUP",
                "message": (
                    "Pending-order inventory is above the preferred operating level."
                ),
                "value": pending_orders,
            })

        if overall_score < 70 and total_orders > 0:
            alerts.append({
                "severity": "CRITICAL",
                "code": "POOR_EXECUTION_HEALTH",
                "message": (
                    "Overall execution health has fallen below acceptable levels."
                ),
                "value": round(
                    overall_score,
                    2,
                ),
            })

        # ----------------------------------------------------------
        # Headline and narrative-ready summary
        # ----------------------------------------------------------

        if total_orders == 0:
            headline = (
                "Execution intelligence is awaiting order activity."
            )

        elif alerts:
            headline = (
                f"Execution health is {execution_status.lower()} with "
                f"{len(alerts)} active alert(s)."
            )

        elif overall_score >= 95:
            headline = (
                "Execution quality is operating at an excellent institutional level."
            )

        elif overall_score >= 85:
            headline = (
                "Execution quality is stable with minor optimization opportunities."
            )

        else:
            headline = (
                "Execution quality requires review and active optimization."
            )

        return {
            "summary": {
                "headline": headline,
                "overall_score": round(
                    overall_score,
                    2,
                ),
                "grade": execution_grade,
                "status": execution_status,
                "risk_level": risk_level,
                "alert_count": len(alerts),
                "recommendation_count": len(
                    recommendations
                ),
            },
            "broker_analysis": broker_analysis,
            "execution_analysis": execution_analysis,
            "cost_analysis": cost_analysis,
            "risk_analysis": risk_analysis,
            "recommendations": recommendations,
            "alerts": alerts,
            "generated_at": datetime.now(
                timezone.utc,
            ).isoformat(),
        }

    # -------------------------------------------------------------------------
    # Broker Ranking
    # -------------------------------------------------------------------------

    def broker_rankings(
        self,
        *,
        account_id=None,
        portfolio_id=None,
    ):

        packet = self.build_execution_packet(

            account_id=account_id,

            portfolio_id=portfolio_id,

        )

        broker = packet["broker"]

        return [

            {

                "broker": "Paper",

                "score": broker.get(

                    "broker_score",

                    0,

                ),

                "latency_ms": broker.get(

                    "average_latency_ms",

                    0,

                ),

                "slippage": broker.get(

                    "average_slippage",

                    0,

                ),

                "fill_rate": broker.get(

                    "fill_rate",

                    0,

                ),

            }

        ]

    # -------------------------------------------------------------------------
    # Executive AI Summary
    # -------------------------------------------------------------------------

    def executive_ai_summary(
        self,
        *,
        account_id=None,
        portfolio_id=None,
    ):

        health = self.execution_health(

            account_id=account_id,

            portfolio_id=portfolio_id,

        )

        observations = []

        if health["status"] == "GREEN":

            observations.append(

                "Execution quality is operating within institutional thresholds."

            )

        if health["latency_ms"] > 250:

            observations.append(

                "Execution latency is elevated."

            )

        if abs(

            health["slippage"]

        ) > 0.00020:

            observations.append(

                "Average slippage exceeds target."

            )

        if not observations:

            observations.append(

                "Execution performance is stable."

            )

        return {

            "headline":

                f"Execution Grade: {health['grade']}",

            "health": health,

            "observations": observations,

            "generated_at": datetime.now(

                timezone.utc,

            ).isoformat(),

        }

# ---------------------------------------------------------
# Singleton
# ---------------------------------------------------------

_ENGINE = None


def get_forex_execution_analytics_engine(db=None):
    global _ENGINE

    if _ENGINE is None:
        _ENGINE = ForexExecutionAnalyticsEngine(db=db)

    elif db is not None:
        _ENGINE.db = db

    return _ENGINE