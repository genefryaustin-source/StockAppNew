"""
Institutional Trade Attribution Service

Consumes immutable execution events and determines
why a trade succeeded or failed.

This service NEVER executes trades.

Execution Events
        ↓
Trade Attribution
        ↓
AI Review
        ↓
Performance Analytics
"""

from __future__ import annotations

import logging

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Dict, Optional

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


# ==========================================================
# Attribution Result
# ==========================================================


@dataclass(slots=True)
class TradeAttribution:

    order_id: Optional[int]

    position_id: Optional[int]

    symbol: str

    side: str

    entry_price: float

    exit_price: float

    quantity: float

    realized_pnl: float

    return_pct: float

    holding_minutes: float

    execution_score: float

    strategy_score: float

    timing_score: float

    risk_score: float

    overall_score: float

    grade: str

    strengths: list[str]

    weaknesses: list[str]

    generated_at: datetime


# ==========================================================
# Service
# ==========================================================


class StockTradeAttributionService:

    """
    Institutional trade attribution engine.
    """

    def __init__(self, db):

        self.db = db

        self._ensure_tables()

    # ======================================================
    # Bootstrap
    # ======================================================

    def _ensure_tables(self):

        if self.db is None:
            return

        try:

            self.db.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS stock_trade_attribution (

                        id BIGSERIAL PRIMARY KEY,

                        order_id BIGINT,

                        position_id BIGINT,

                        symbol VARCHAR(20),

                        side VARCHAR(10),

                        entry_price DOUBLE PRECISION,

                        exit_price DOUBLE PRECISION,

                        quantity DOUBLE PRECISION,

                        realized_pnl DOUBLE PRECISION,

                        return_pct DOUBLE PRECISION,

                        holding_minutes DOUBLE PRECISION,

                        execution_score DOUBLE PRECISION,

                        strategy_score DOUBLE PRECISION,

                        timing_score DOUBLE PRECISION,

                        risk_score DOUBLE PRECISION,

                        overall_score DOUBLE PRECISION,

                        grade VARCHAR(5),

                        strengths TEXT,

                        weaknesses TEXT,

                        generated_at TIMESTAMP
                    )
                    """
                )
            )

            self.db.commit()

        except SQLAlchemyError:

            logger.exception(
                "Unable to initialize attribution tables."
            )

            try:
                self.db.rollback()
            except Exception:
                pass

    # ======================================================
    # Public API
    # ======================================================

    def analyze_trade(
        self,
        *,
        order: Any,
        position: Any,
    ) -> TradeAttribution:
        """
        Full attribution implementation
        continues in Part 2.
        """

        return TradeAttribution(

            order_id=getattr(order, "id", None),

            position_id=getattr(position, "id", None),

            symbol=getattr(order, "symbol", ""),

            side=getattr(order, "side", ""),

            entry_price=0.0,

            exit_price=0.0,

            quantity=0.0,

            realized_pnl=0.0,

            return_pct=0.0,

            holding_minutes=0.0,

            execution_score=0.0,

            strategy_score=0.0,

            timing_score=0.0,

            risk_score=0.0,

            overall_score=0.0,

            grade="NR",

            strengths=[],

            weaknesses=[],

            generated_at=datetime.now(UTC),
        )
    # ======================================================
    # Score Calculations
    # ======================================================

    def _execution_score(
        self,
        *,
        entry_price: float,
        expected_price: float,
    ) -> float:
        """
        Measures execution quality versus expected fill.
        """

        if expected_price <= 0:
            return 100.0

        slippage = abs(entry_price - expected_price) / expected_price

        score = 100.0 - (slippage * 1000)

        return max(0.0, min(100.0, score))

    def _strategy_score(
        self,
        *,
        realized_pnl: float,
        return_pct: float,
    ) -> float:
        """
        Measures profitability.
        """

        score = 50.0

        score += return_pct * 4

        if realized_pnl > 0:
            score += 20

        return max(0.0, min(100.0, score))

    def _timing_score(
        self,
        *,
        holding_minutes: float,
        realized_pnl: float,
    ) -> float:
        """
        Measures trade timing.
        """

        score = 70.0

        if holding_minutes < 1:
            score -= 20

        elif holding_minutes > 1440:
            score -= 5

        if realized_pnl > 0:
            score += 15

        return max(0.0, min(100.0, score))

    def _risk_score(
        self,
        *,
        realized_pnl: float,
        max_risk: float,
    ) -> float:
        """
        Measures adherence to risk.
        """

        if max_risk <= 0:
            return 100.0

        utilization = abs(realized_pnl) / max_risk

        score = 100.0

        if utilization > 1.0:
            score -= (utilization - 1.0) * 30

        return max(0.0, min(100.0, score))

    def _overall_score(
        self,
        *,
        execution_score: float,
        strategy_score: float,
        timing_score: float,
        risk_score: float,
    ) -> float:

        return round(

            (
                execution_score * 0.25
                + strategy_score * 0.35
                + timing_score * 0.20
                + risk_score * 0.20
            ),

            2,
        )

    def _grade(
        self,
        score: float,
    ) -> str:

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
    # Public API
    # ======================================================

    def analyze_trade(
        self,
        *,
        order: Any,
        position: Any,
    ) -> TradeAttribution:

        # A completed round-trip (this fill closed or reduced an existing
        # position) carries its own entry/exit/PnL/holding-period data on
        # the ClosedTrade record OrderService produced for this fill. That
        # is the correct per-trade source -- position.realized_pnl is a
        # lifetime running total across every trade in the symbol, not
        # this trade's result, and would badly distort attribution once a
        # position has more than one round trip in its history.
        closed_trade = getattr(order, "closed_trade", None)

        if closed_trade is not None:

            entry_price = float(getattr(closed_trade, "entry_price", 0.0) or 0.0)
            exit_price = float(getattr(closed_trade, "exit_price", entry_price) or entry_price)
            quantity = float(getattr(closed_trade, "exit_qty", 0.0) or 0.0)
            realized_pnl = float(getattr(closed_trade, "net_pnl", 0.0) or 0.0)

            opened = getattr(closed_trade, "opened_at", None)
            closed = getattr(closed_trade, "closed_at", None)

            if opened and closed:
                holding_minutes = (closed - opened).total_seconds() / 60
            else:
                holding_minutes = 0.0

        else:

            # Opening or adding to a position: this fill has an entry
            # price but nothing has been realized or closed out yet.
            entry_price = float(getattr(order, "avg_fill_price", 0.0) or 0.0)
            exit_price = entry_price
            quantity = float(getattr(order, "filled_qty", 0.0) or 0.0)
            realized_pnl = 0.0
            holding_minutes = 0.0

        # No independently recorded reference/expected price exists yet
        # for this order (the paper broker doesn't model a bid/ask spread
        # or price impact, so there is nothing meaningful to compare
        # against). Treat execution quality as neutral rather than
        # inventing a slippage figure from data that isn't there.
        expected_price = entry_price

        return_pct = 0.0

        if entry_price > 0:
            return_pct = ((exit_price - entry_price) / entry_price) * 100

        planned_risk = getattr(order, "planned_risk", None)
        planned_risk = float(planned_risk) if planned_risk is not None else 0.0

        execution_score = self._execution_score(
            entry_price=entry_price,
            expected_price=expected_price,
        )

        strategy_score = self._strategy_score(
            realized_pnl=realized_pnl,
            return_pct=return_pct,
        )

        timing_score = self._timing_score(
            holding_minutes=holding_minutes,
            realized_pnl=realized_pnl,
        )

        risk_score = self._risk_score(
            realized_pnl=realized_pnl,
            max_risk=planned_risk,
        )

        overall_score = self._overall_score(
            execution_score=execution_score,
            strategy_score=strategy_score,
            timing_score=timing_score,
            risk_score=risk_score,
        )

        grade = self._grade(
            overall_score,
        )

        strengths: list[str] = []

        weaknesses: list[str] = []

        if execution_score >= 90:
            strengths.append("Excellent execution quality")
        else:
            weaknesses.append("Execution slippage")

        if timing_score >= 90:
            strengths.append("Excellent trade timing")
        else:
            weaknesses.append("Entry/exit timing")

        if strategy_score >= 90:
            strengths.append("Strong strategy performance")
        else:
            weaknesses.append("Low strategy effectiveness")

        if risk_score >= 90:
            strengths.append("Excellent risk management")
        else:
            weaknesses.append("Risk exceeded plan")

        return TradeAttribution(

            order_id=getattr(order, "id", None),

            position_id=getattr(position, "id", None),

            symbol=getattr(order, "symbol", ""),

            side=getattr(order, "side", ""),

            entry_price=entry_price,

            exit_price=exit_price,

            quantity=quantity,

            realized_pnl=realized_pnl,

            return_pct=round(return_pct, 2),

            holding_minutes=round(
                holding_minutes,
                2,
            ),

            execution_score=round(
                execution_score,
                2,
            ),

            strategy_score=round(
                strategy_score,
                2,
            ),

            timing_score=round(
                timing_score,
                2,
            ),

            risk_score=round(
                risk_score,
                2,
            ),

            overall_score=overall_score,

            grade=grade,

            strengths=strengths,

            weaknesses=weaknesses,

            generated_at=datetime.now(UTC),
        )

    # ======================================================
    # Persistence
    # ======================================================

    def _persist_attribution(
            self,
            attribution: TradeAttribution,
    ) -> None:
        """
        Persist a completed trade attribution record.
        """

        if self.db is None:
            return

        try:

            self.db.execute(

                text(
                    """
                    INSERT INTO stock_trade_attribution (

                        order_id,
                        position_id,

                        symbol,
                        side,

                        entry_price,
                        exit_price,
                        quantity,

                        realized_pnl,
                        return_pct,

                        holding_minutes,

                        execution_score,
                        strategy_score,
                        timing_score,
                        risk_score,

                        overall_score,

                        grade,

                        strengths,
                        weaknesses,

                        generated_at

                    )
                    VALUES (

                        :order_id,
                        :position_id,

                        :symbol,
                        :side,

                        :entry_price,
                        :exit_price,
                        :quantity,

                        :realized_pnl,
                        :return_pct,

                        :holding_minutes,

                        :execution_score,
                        :strategy_score,
                        :timing_score,
                        :risk_score,

                        :overall_score,

                        :grade,

                        :strengths,
                        :weaknesses,

                        :generated_at
                    )
                    """
                ),

                {

                    "order_id":
                        attribution.order_id,

                    "position_id":
                        attribution.position_id,

                    "symbol":
                        attribution.symbol,

                    "side":
                        attribution.side,

                    "entry_price":
                        attribution.entry_price,

                    "exit_price":
                        attribution.exit_price,

                    "quantity":
                        attribution.quantity,

                    "realized_pnl":
                        attribution.realized_pnl,

                    "return_pct":
                        attribution.return_pct,

                    "holding_minutes":
                        attribution.holding_minutes,

                    "execution_score":
                        attribution.execution_score,

                    "strategy_score":
                        attribution.strategy_score,

                    "timing_score":
                        attribution.timing_score,

                    "risk_score":
                        attribution.risk_score,

                    "overall_score":
                        attribution.overall_score,

                    "grade":
                        attribution.grade,

                    "strengths":
                        "\n".join(
                            attribution.strengths,
                        ),

                    "weaknesses":
                        "\n".join(
                            attribution.weaknesses,
                        ),

                    "generated_at":
                        attribution.generated_at,
                },
            )

            self.db.commit()

        except SQLAlchemyError:

            logger.exception(
                "Unable to persist trade attribution."
            )

            try:
                self.db.rollback()
            except Exception:
                pass

    # ======================================================
    # Query API
    # ======================================================

    def get_trade_attribution(
            self,
            *,
            order_id: Optional[int] = None,
            position_id: Optional[int] = None,
            symbol: Optional[str] = None,
            limit: int = 250,
    ) -> list[dict]:
        """
        Return attribution records.
        """

        if self.db is None:
            return []

        sql = """
            SELECT *
            FROM stock_trade_attribution
            WHERE 1=1
        """

        params: Dict[str, Any] = {}

        if order_id is not None:
            sql += " AND order_id=:order_id"

            params["order_id"] = order_id

        if position_id is not None:
            sql += " AND position_id=:position_id"

            params["position_id"] = position_id

        if symbol:
            sql += " AND UPPER(symbol)=:symbol"

            params["symbol"] = symbol.upper()

        sql += """
            ORDER BY generated_at DESC
            LIMIT :limit
        """

        params["limit"] = limit

        try:

            rows = (

                self.db.execute(
                    text(sql),
                    params,
                )

                .mappings()

                .all()

            )

            return [

                dict(r)

                for r in rows

            ]

        except SQLAlchemyError:

            logger.exception(
                "Unable to load trade attribution."
            )

            return []

    # ======================================================
    # Dashboard Summary
    # ======================================================

    def summary(
            self,
    ) -> Dict[str, Any]:
        """
        Executive summary for dashboards.
        """

        records = self.get_trade_attribution(
            limit=100000,
        )

        if not records:
            return {

                "trade_count": 0,

                "average_score": 0.0,

                "average_return": 0.0,

                "average_pnl": 0.0,

                "grades": {},
            }

        trade_count = len(records)

        average_score = sum(
            r["overall_score"]
            for r in records
        ) / trade_count

        average_return = sum(
            r["return_pct"]
            for r in records
        ) / trade_count

        average_pnl = sum(
            r["realized_pnl"]
            for r in records
        ) / trade_count

        grades: Dict[str, int] = {}

        for row in records:
            grade = row["grade"]

            grades[grade] = grades.get(
                grade,
                0,
            ) + 1

        return {

            "trade_count":
                trade_count,

            "average_score":
                round(
                    average_score,
                    2,
                ),

            "average_return":
                round(
                    average_return,
                    2,
                ),

            "average_pnl":
                round(
                    average_pnl,
                    2,
                ),

            "grades":
                grades,
        }

    # ======================================================
    # Factory
    # ======================================================

_trade_attribution_service = None

def get_stock_trade_attribution_service(
        db,
) -> StockTradeAttributionService:

    global _trade_attribution_service

    if (

            _trade_attribution_service is None

            or _trade_attribution_service.db is not db

    ):
        _trade_attribution_service = (

            StockTradeAttributionService(
                db,
            )

        )

    return _trade_attribution_service