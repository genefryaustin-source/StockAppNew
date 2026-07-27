"""
modules/stocks/stock_broker_analytics_service.py

Stock Broker Analytics Service

Aggregates execution quality (from StockExecutionQualityService) and
order reliability (rejection rate, from StockExecutionEventService) by
broker, so a client with more than one broker configured can see which
one is actually executing better for them, not just how a single trade
went.

Caveat, and an important one: modules.portfolio.order_service.OrderService
currently hardcodes every stock order to execute through its internal
simulated paper logic regardless of which broker object it was
constructed with -- the broker selector in the trading UI doesn't yet
route real orders to Alpaca/Tradier/IBKR. Until that routing exists,
every persisted execution-quality record will show broker="paper", and
this service will correctly report there is exactly one broker with any
data. That's not a bug here -- it's an honest reflection of what
currently executes. This service is built to compare multiple brokers
correctly the moment real multi-broker routing exists; it doesn't need
to change when that happens.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, UTC
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from modules.stocks.stock_execution_quality_service import (
    get_stock_execution_quality_service,
)
from modules.stocks.stock_execution_event_service import (
    get_stock_execution_event_service,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class BrokerAnalyticsRecord:
    broker: str
    portfolio_id: Optional[str]

    order_count: int
    rejected_count: int
    rejection_rate: float

    average_slippage_bps: float
    average_commission_bps: float
    average_total_cost_bps: float
    average_fill_rate: float
    average_latency_ms: float

    average_quality_score: float
    grade_distribution: Dict[str, int]

    reliability_rating: str
    overall_grade: str

    generated_at: datetime


class StockBrokerAnalyticsService:

    def __init__(self, db):
        self.db = db
        self.quality_service = get_stock_execution_quality_service(db)
        self.execution_events = get_stock_execution_event_service(db)
        self._ensure_tables()

    # ======================================================
    # Bootstrap
    # ======================================================

    def _ensure_tables(self) -> None:
        if self.db is None:
            return

        try:
            self.db.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS stock_broker_analytics (

                        id BIGSERIAL PRIMARY KEY,

                        broker VARCHAR(50),
                        portfolio_id VARCHAR(36),

                        order_count INTEGER,
                        rejected_count INTEGER,
                        rejection_rate DOUBLE PRECISION,

                        average_slippage_bps DOUBLE PRECISION,
                        average_commission_bps DOUBLE PRECISION,
                        average_total_cost_bps DOUBLE PRECISION,
                        average_fill_rate DOUBLE PRECISION,
                        average_latency_ms DOUBLE PRECISION,

                        average_quality_score DOUBLE PRECISION,
                        grade_distribution TEXT,

                        reliability_rating VARCHAR(10),
                        overall_grade VARCHAR(5),

                        generated_at TIMESTAMP
                    )
                    """
                )
            )
            self.db.commit()

        except SQLAlchemyError:
            logger.exception("Unable to initialize stock_broker_analytics table.")
            try:
                self.db.rollback()
            except Exception:
                pass

    # ======================================================
    # Analysis
    # ======================================================

    def analyze_broker(
        self,
        broker: str,
        *,
        portfolio_id: Optional[str] = None,
    ) -> BrokerAnalyticsRecord:
        """
        Pure computation over currently-persisted quality and event
        records for one broker. Does not write anything.
        """

        quality_records = self.quality_service.get_quality_records(
            portfolio_id=portfolio_id,
            broker=broker,
            limit=100000,
        )

        rejected_events = self.execution_events.get_events(
            portfolio_id=portfolio_id,
            event_type="ORDER_REJECTED",
            limit=100000,
        )
        rejected_count = sum(
            1 for e in rejected_events if e.get("broker") == broker
        )

        order_count = len(quality_records)
        total_attempts = order_count + rejected_count

        rejection_rate = (
            (rejected_count / total_attempts * 100.0) if total_attempts else 0.0
        )

        if order_count == 0:
            average_slippage_bps = 0.0
            average_commission_bps = 0.0
            average_total_cost_bps = 0.0
            average_fill_rate = 0.0
            average_latency_ms = 0.0
            average_quality_score = 0.0
            grade_distribution: Dict[str, int] = {}
        else:
            average_slippage_bps = sum(r["slippage_bps"] for r in quality_records) / order_count
            average_commission_bps = sum(r["commission_bps"] for r in quality_records) / order_count
            average_total_cost_bps = sum(r["total_cost_bps"] for r in quality_records) / order_count
            average_fill_rate = sum(r["fill_rate"] for r in quality_records) / order_count
            average_latency_ms = sum(r["latency_ms"] for r in quality_records) / order_count
            average_quality_score = sum(r["quality_score"] for r in quality_records) / order_count

            grade_distribution = {}
            for r in quality_records:
                grade_distribution[r["grade"]] = grade_distribution.get(r["grade"], 0) + 1

        reliability_rating = self._reliability_rating(rejection_rate)
        overall_grade = self._grade(
            self._overall_score(average_quality_score, rejection_rate)
        )

        return BrokerAnalyticsRecord(
            broker=broker,
            portfolio_id=portfolio_id,
            order_count=order_count,
            rejected_count=rejected_count,
            rejection_rate=round(rejection_rate, 2),
            average_slippage_bps=round(average_slippage_bps, 2),
            average_commission_bps=round(average_commission_bps, 2),
            average_total_cost_bps=round(average_total_cost_bps, 2),
            average_fill_rate=round(average_fill_rate, 2),
            average_latency_ms=round(average_latency_ms, 2),
            average_quality_score=round(average_quality_score, 2),
            grade_distribution=grade_distribution,
            reliability_rating=reliability_rating,
            overall_grade=overall_grade,
            generated_at=datetime.now(UTC),
        )

    def analyze_all_brokers(
        self,
        *,
        portfolio_id: Optional[str] = None,
    ) -> List[BrokerAnalyticsRecord]:
        """
        One record per broker with any history (fills or rejections),
        sorted best quality score first.
        """

        brokers = self._known_brokers(portfolio_id=portfolio_id)

        records = [
            self.analyze_broker(broker, portfolio_id=portfolio_id)
            for broker in brokers
        ]

        records.sort(key=lambda r: r.average_quality_score, reverse=True)
        return records

    def _known_brokers(self, *, portfolio_id: Optional[str]) -> List[str]:
        brokers = set()

        for r in self.quality_service.get_quality_records(
            portfolio_id=portfolio_id, limit=100000
        ):
            if r.get("broker"):
                brokers.add(r["broker"])

        for e in self.execution_events.get_events(
            portfolio_id=portfolio_id, event_type="ORDER_REJECTED", limit=100000
        ):
            if e.get("broker"):
                brokers.add(e["broker"])

        return sorted(brokers)

    @staticmethod
    def _overall_score(average_quality_score: float, rejection_rate: float) -> float:
        score = average_quality_score

        if rejection_rate > 50:
            score -= 30
        elif rejection_rate > 25:
            score -= 15
        elif rejection_rate > 10:
            score -= 7

        return max(0.0, min(100.0, score))

    @staticmethod
    def _reliability_rating(rejection_rate: float) -> str:
        if rejection_rate <= 1:
            return "EXCELLENT"
        if rejection_rate <= 5:
            return "GOOD"
        if rejection_rate <= 15:
            return "FAIR"
        if rejection_rate <= 30:
            return "POOR"

        return "CRITICAL"

    @staticmethod
    def _grade(score: float) -> str:
        if score >= 97:
            return "A+"
        if score >= 93:
            return "A"
        if score >= 90:
            return "A-"
        if score >= 87:
            return "B+"
        if score >= 83:
            return "B"
        if score >= 80:
            return "B-"
        if score >= 77:
            return "C+"
        if score >= 73:
            return "C"
        if score >= 70:
            return "C-"
        if score >= 60:
            return "D"

        return "F"

    # ======================================================
    # Persistence
    # ======================================================

    def record_snapshot(
        self,
        *,
        portfolio_id: Optional[str] = None,
    ) -> List[BrokerAnalyticsRecord]:
        """
        Compute and persist a timestamped snapshot for every broker with
        history. Intended to be called periodically (a scheduled job or a
        dashboard refresh action), not after every order -- this is a
        rollup over potentially many orders, not a per-order fact.
        """

        records = self.analyze_all_brokers(portfolio_id=portfolio_id)

        for record in records:
            self._persist_snapshot(record)

        return records

    def _persist_snapshot(self, record: BrokerAnalyticsRecord) -> None:
        if self.db is None:
            return

        try:
            import json

            self.db.execute(
                text(
                    """
                    INSERT INTO stock_broker_analytics (

                        broker,
                        portfolio_id,

                        order_count,
                        rejected_count,
                        rejection_rate,

                        average_slippage_bps,
                        average_commission_bps,
                        average_total_cost_bps,
                        average_fill_rate,
                        average_latency_ms,

                        average_quality_score,
                        grade_distribution,

                        reliability_rating,
                        overall_grade,

                        generated_at

                    )
                    VALUES (

                        :broker,
                        :portfolio_id,

                        :order_count,
                        :rejected_count,
                        :rejection_rate,

                        :average_slippage_bps,
                        :average_commission_bps,
                        :average_total_cost_bps,
                        :average_fill_rate,
                        :average_latency_ms,

                        :average_quality_score,
                        :grade_distribution,

                        :reliability_rating,
                        :overall_grade,

                        :generated_at
                    )
                    """
                ),
                {
                    "broker": record.broker,
                    "portfolio_id": record.portfolio_id,
                    "order_count": record.order_count,
                    "rejected_count": record.rejected_count,
                    "rejection_rate": record.rejection_rate,
                    "average_slippage_bps": record.average_slippage_bps,
                    "average_commission_bps": record.average_commission_bps,
                    "average_total_cost_bps": record.average_total_cost_bps,
                    "average_fill_rate": record.average_fill_rate,
                    "average_latency_ms": record.average_latency_ms,
                    "average_quality_score": record.average_quality_score,
                    "grade_distribution": json.dumps(record.grade_distribution),
                    "reliability_rating": record.reliability_rating,
                    "overall_grade": record.overall_grade,
                    "generated_at": record.generated_at,
                },
            )

            self.db.commit()

        except SQLAlchemyError:
            logger.exception("Unable to persist broker analytics snapshot.")
            try:
                self.db.rollback()
            except Exception:
                pass

    # ======================================================
    # Query API
    # ======================================================

    def get_snapshots(
        self,
        *,
        broker: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        limit: int = 250,
    ) -> List[Dict[str, Any]]:

        if self.db is None:
            return []

        sql = """
            SELECT *
            FROM stock_broker_analytics
            WHERE 1=1
        """

        params: Dict[str, Any] = {}

        if broker:
            sql += " AND broker=:broker"
            params["broker"] = broker

        if portfolio_id:
            sql += " AND portfolio_id=:portfolio_id"
            params["portfolio_id"] = portfolio_id

        sql += """
            ORDER BY generated_at DESC
            LIMIT :limit
        """

        params["limit"] = limit

        try:
            rows = (
                self.db.execute(text(sql), params)
                .mappings()
                .all()
            )

            return [dict(row) for row in rows]

        except SQLAlchemyError:
            logger.exception("Unable to load broker analytics snapshots.")
            return []

    # ======================================================
    # Dashboard Summary
    # ======================================================

    def best_broker(self, *, portfolio_id: Optional[str] = None) -> Optional[str]:
        """
        The broker with the highest average quality score among brokers
        with at least one filled order. None if there's no data yet.
        """

        records = [
            r for r in self.analyze_all_brokers(portfolio_id=portfolio_id)
            if r.order_count > 0
        ]

        if not records:
            return None

        return records[0].broker

    def summary(self, *, portfolio_id: Optional[str] = None) -> Dict[str, Any]:
        records = self.analyze_all_brokers(portfolio_id=portfolio_id)

        if not records:
            return {
                "broker_count": 0,
                "best_broker": None,
                "best_broker_score": 0.0,
                "brokers": {},
            }

        with_orders = [r for r in records if r.order_count > 0]
        best = with_orders[0] if with_orders else None

        return {
            "broker_count": len(records),
            "best_broker": best.broker if best else None,
            "best_broker_score": best.average_quality_score if best else 0.0,
            "brokers": {
                r.broker: {
                    "order_count": r.order_count,
                    "quality_score": r.average_quality_score,
                    "grade": r.overall_grade,
                    "rejection_rate": r.rejection_rate,
                    "reliability_rating": r.reliability_rating,
                }
                for r in records
            },
        }


_broker_analytics_service = None


def get_stock_broker_analytics_service(db) -> StockBrokerAnalyticsService:
    global _broker_analytics_service

    if (
        _broker_analytics_service is None
        or _broker_analytics_service.db is not db
    ):
        _broker_analytics_service = StockBrokerAnalyticsService(db)

    return _broker_analytics_service