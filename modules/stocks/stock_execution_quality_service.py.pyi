"""
modules/stocks/stock_execution_quality_service.py

Stock Execution Quality Service

Analyzes filled stock orders for execution quality -- slippage cost,
commission cost, and fill completeness -- expressed in basis points so
results are comparable across symbols and price levels.

This is a read-side analytics service, not a participant in
StockTradingService's post-execution pipeline. It analyzes orders that
have already been executed and persisted elsewhere (TradeOrder rows);
dashboards and batch jobs call it directly, on demand.

Caveat: the current paper broker fills every order synchronously at the
exact reference price it just read, with no simulated spread, market
impact, or network delay. actual_slippage and latency_ms will read as
zero for every paper trade as an honest reflection of that broker
simulation, not a bug in this service. Once a broker models real price
impact or asynchronous fills, these numbers will start carrying signal.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, UTC
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ExecutionQualityRecord:
    order_id: Optional[int]
    portfolio_id: Optional[str]

    symbol: str
    side: str
    broker: Optional[str]

    requested_qty: float
    filled_qty: float
    fill_rate: float

    avg_fill_price: float

    slippage_amount: float
    slippage_bps: float

    commission_amount: float
    commission_bps: float

    total_cost_bps: float

    latency_ms: float

    slippage_rating: str
    commission_rating: str
    fill_rating: str

    quality_score: float
    grade: str

    generated_at: datetime


class StockExecutionQualityService:

    def __init__(self, db):
        self.db = db
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
                    CREATE TABLE IF NOT EXISTS stock_execution_quality (

                        id BIGSERIAL PRIMARY KEY,

                        order_id BIGINT,
                        portfolio_id VARCHAR(36),

                        symbol VARCHAR(20),
                        side VARCHAR(10),
                        broker VARCHAR(50),

                        requested_qty DOUBLE PRECISION,
                        filled_qty DOUBLE PRECISION,
                        fill_rate DOUBLE PRECISION,

                        avg_fill_price DOUBLE PRECISION,

                        slippage_amount DOUBLE PRECISION,
                        slippage_bps DOUBLE PRECISION,

                        commission_amount DOUBLE PRECISION,
                        commission_bps DOUBLE PRECISION,

                        total_cost_bps DOUBLE PRECISION,

                        latency_ms DOUBLE PRECISION,

                        slippage_rating VARCHAR(10),
                        commission_rating VARCHAR(10),
                        fill_rating VARCHAR(15),

                        quality_score DOUBLE PRECISION,
                        grade VARCHAR(5),

                        generated_at TIMESTAMP
                    )
                    """
                )
            )
            self.db.commit()

        except SQLAlchemyError:
            logger.exception("Unable to initialize execution quality tables.")
            try:
                self.db.rollback()
            except Exception:
                pass

    # ======================================================
    # Analysis
    # ======================================================

    def analyze_order(self, order: Any) -> ExecutionQualityRecord:
        """
        Pure computation over a filled order. Accepts anything with the
        right attributes (a TradeOrder row, or a duck-typed stand-in),
        does not touch the database.
        """

        symbol = str(getattr(order, "symbol", "") or "")
        side = str(getattr(order, "side", "") or "")
        broker = getattr(order, "broker", None)

        requested_qty = abs(float(getattr(order, "qty", 0.0) or 0.0))
        filled_qty = abs(float(getattr(order, "filled_qty", 0.0) or 0.0))

        fill_rate = (
            (filled_qty / requested_qty * 100.0)
            if requested_qty > 0
            else 0.0
        )

        avg_fill_price = float(getattr(order, "avg_fill_price", 0.0) or 0.0)
        notional = filled_qty * avg_fill_price

        slippage_amount = float(getattr(order, "actual_slippage", 0.0) or 0.0)
        slippage_bps = (
            (slippage_amount / notional) * 10000.0
            if notional > 0
            else 0.0
        )

        commission_amount = float(getattr(order, "actual_commission", 0.0) or 0.0)
        commission_bps = (
            (commission_amount / notional) * 10000.0
            if notional > 0
            else 0.0
        )

        total_cost_bps = slippage_bps + commission_bps

        latency_ms = self._latency_ms(order)

        slippage_rating = self._slippage_rating(slippage_bps)
        commission_rating = self._commission_rating(commission_bps)
        fill_rating = self._fill_rating(fill_rate)

        quality_score = self._score(
            slippage_bps=slippage_bps,
            commission_bps=commission_bps,
            fill_rate=fill_rate,
        )

        return ExecutionQualityRecord(
            order_id=getattr(order, "id", None),
            portfolio_id=getattr(order, "portfolio_id", None),
            symbol=symbol,
            side=side,
            broker=broker,
            requested_qty=round(requested_qty, 4),
            filled_qty=round(filled_qty, 4),
            fill_rate=round(fill_rate, 2),
            avg_fill_price=round(avg_fill_price, 4),
            slippage_amount=round(slippage_amount, 4),
            slippage_bps=round(slippage_bps, 2),
            commission_amount=round(commission_amount, 4),
            commission_bps=round(commission_bps, 2),
            total_cost_bps=round(total_cost_bps, 2),
            latency_ms=round(latency_ms, 2) if latency_ms is not None else 0.0,
            slippage_rating=slippage_rating,
            commission_rating=commission_rating,
            fill_rating=fill_rating,
            quality_score=quality_score,
            grade=self._grade(quality_score),
            generated_at=datetime.now(UTC),
        )

    def analyze_orders(self, orders: Iterable[Any]) -> List[ExecutionQualityRecord]:
        return [self.analyze_order(order) for order in orders]

    def record_order(self, order: Any) -> ExecutionQualityRecord:
        """Analyze and persist in a single call."""
        record = self.analyze_order(order)
        self._persist_quality_record(record)
        return record

    @staticmethod
    def _latency_ms(order: Any) -> Optional[float]:
        submitted = getattr(order, "submitted_at", None)
        filled = getattr(order, "filled_at", None)

        if submitted is None or filled is None:
            return None

        try:
            delta_ms = (filled - submitted).total_seconds() * 1000.0
        except TypeError:
            return None

        return delta_ms if delta_ms >= 0 else None

    @staticmethod
    def _slippage_rating(value_bps: float) -> str:
        value = abs(value_bps)

        if value <= 2:
            return "EXCELLENT"
        if value <= 5:
            return "GOOD"
        if value <= 10:
            return "FAIR"
        if value <= 25:
            return "POOR"

        return "CRITICAL"

    @staticmethod
    def _commission_rating(value_bps: float) -> str:
        value = abs(value_bps)

        if value <= 1:
            return "EXCELLENT"
        if value <= 3:
            return "GOOD"
        if value <= 8:
            return "FAIR"
        if value <= 20:
            return "POOR"

        return "CRITICAL"

    @staticmethod
    def _fill_rating(fill_rate: float) -> str:
        if fill_rate >= 100:
            return "COMPLETE"
        if fill_rate >= 75:
            return "MOSTLY_FILLED"
        if fill_rate >= 25:
            return "PARTIAL"
        if fill_rate > 0:
            return "MINIMAL"

        return "UNFILLED"

    @staticmethod
    def _score(
        *,
        slippage_bps: float,
        commission_bps: float,
        fill_rate: float,
    ) -> float:
        score = 100.0

        abs_slippage = abs(slippage_bps)
        if abs_slippage > 25:
            score -= 35
        elif abs_slippage > 10:
            score -= 25
        elif abs_slippage > 5:
            score -= 15
        elif abs_slippage > 2:
            score -= 7

        abs_commission = abs(commission_bps)
        if abs_commission > 20:
            score -= 25
        elif abs_commission > 8:
            score -= 15
        elif abs_commission > 3:
            score -= 8
        elif abs_commission > 1:
            score -= 3

        if fill_rate < 100:
            score -= (100.0 - fill_rate) * 0.3

        return round(max(0.0, min(100.0, score)), 2)

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

    def _persist_quality_record(self, record: ExecutionQualityRecord) -> None:
        if self.db is None:
            return

        try:
            self.db.execute(
                text(
                    """
                    INSERT INTO stock_execution_quality (

                        order_id,
                        portfolio_id,

                        symbol,
                        side,
                        broker,

                        requested_qty,
                        filled_qty,
                        fill_rate,

                        avg_fill_price,

                        slippage_amount,
                        slippage_bps,

                        commission_amount,
                        commission_bps,

                        total_cost_bps,

                        latency_ms,

                        slippage_rating,
                        commission_rating,
                        fill_rating,

                        quality_score,
                        grade,

                        generated_at

                    )
                    VALUES (

                        :order_id,
                        :portfolio_id,

                        :symbol,
                        :side,
                        :broker,

                        :requested_qty,
                        :filled_qty,
                        :fill_rate,

                        :avg_fill_price,

                        :slippage_amount,
                        :slippage_bps,

                        :commission_amount,
                        :commission_bps,

                        :total_cost_bps,

                        :latency_ms,

                        :slippage_rating,
                        :commission_rating,
                        :fill_rating,

                        :quality_score,
                        :grade,

                        :generated_at
                    )
                    """
                ),
                {
                    "order_id": record.order_id,
                    "portfolio_id": record.portfolio_id,
                    "symbol": record.symbol,
                    "side": record.side,
                    "broker": record.broker,
                    "requested_qty": record.requested_qty,
                    "filled_qty": record.filled_qty,
                    "fill_rate": record.fill_rate,
                    "avg_fill_price": record.avg_fill_price,
                    "slippage_amount": record.slippage_amount,
                    "slippage_bps": record.slippage_bps,
                    "commission_amount": record.commission_amount,
                    "commission_bps": record.commission_bps,
                    "total_cost_bps": record.total_cost_bps,
                    "latency_ms": record.latency_ms,
                    "slippage_rating": record.slippage_rating,
                    "commission_rating": record.commission_rating,
                    "fill_rating": record.fill_rating,
                    "quality_score": record.quality_score,
                    "grade": record.grade,
                    "generated_at": record.generated_at,
                },
            )

            self.db.commit()

        except SQLAlchemyError:
            logger.exception("Unable to persist execution quality record.")
            try:
                self.db.rollback()
            except Exception:
                pass

    # ======================================================
    # Query API
    # ======================================================

    def get_quality_records(
        self,
        *,
        order_id: Optional[int] = None,
        portfolio_id: Optional[str] = None,
        symbol: Optional[str] = None,
        broker: Optional[str] = None,
        limit: int = 250,
    ) -> List[Dict[str, Any]]:

        if self.db is None:
            return []

        sql = """
            SELECT *
            FROM stock_execution_quality
            WHERE 1=1
        """

        params: Dict[str, Any] = {}

        if order_id is not None:
            sql += " AND order_id=:order_id"
            params["order_id"] = order_id

        if portfolio_id:
            sql += " AND portfolio_id=:portfolio_id"
            params["portfolio_id"] = portfolio_id

        if symbol:
            sql += " AND UPPER(symbol)=:symbol"
            params["symbol"] = symbol.upper()

        if broker:
            sql += " AND broker=:broker"
            params["broker"] = broker

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
            logger.exception("Unable to load execution quality records.")
            return []

    # ======================================================
    # Dashboard Summary
    # ======================================================

    def summary(self, *, portfolio_id: Optional[str] = None) -> Dict[str, Any]:
        records = self.get_quality_records(
            portfolio_id=portfolio_id,
            limit=100000,
        )

        if not records:
            return {
                "order_count": 0,
                "average_slippage_bps": 0.0,
                "average_commission_bps": 0.0,
                "average_total_cost_bps": 0.0,
                "average_fill_rate": 0.0,
                "average_quality_score": 0.0,
                "grades": {},
            }

        order_count = len(records)

        average_slippage_bps = sum(r["slippage_bps"] for r in records) / order_count
        average_commission_bps = sum(r["commission_bps"] for r in records) / order_count
        average_total_cost_bps = sum(r["total_cost_bps"] for r in records) / order_count
        average_fill_rate = sum(r["fill_rate"] for r in records) / order_count
        average_quality_score = sum(r["quality_score"] for r in records) / order_count

        grades: Dict[str, int] = {}
        for row in records:
            grade = row["grade"]
            grades[grade] = grades.get(grade, 0) + 1

        return {
            "order_count": order_count,
            "average_slippage_bps": round(average_slippage_bps, 2),
            "average_commission_bps": round(average_commission_bps, 2),
            "average_total_cost_bps": round(average_total_cost_bps, 2),
            "average_fill_rate": round(average_fill_rate, 2),
            "average_quality_score": round(average_quality_score, 2),
            "grades": grades,
        }


_execution_quality_service = None


def get_stock_execution_quality_service(db) -> StockExecutionQualityService:
    global _execution_quality_service

    if (
        _execution_quality_service is None
        or _execution_quality_service.db is not db
    ):
        _execution_quality_service = StockExecutionQualityService(db)

    return _execution_quality_service