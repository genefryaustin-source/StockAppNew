"""
modules/stocks/stock_ai_trade_review_service.py

Institutional AI Trade Review Engine

Consumes:

    • Execution Events
    • Trade Attribution
    • Position Statistics

Produces:

    • Executive Review
    • Trading Coach
    • Execution Analysis
    • Risk Review
    • Improvement Recommendations

This module NEVER executes trades.
"""

from __future__ import annotations

import logging

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


# ==========================================================
# AI Review Result
# ==========================================================


@dataclass(slots=True)
class AITradeReview:

    order_id: Optional[int]

    position_id: Optional[int]

    symbol: str

    side: str

    overall_rating: float

    execution_rating: float

    timing_rating: float

    discipline_rating: float

    risk_rating: float

    confidence: float

    summary: str

    strengths: List[str]

    weaknesses: List[str]

    recommendations: List[str]

    generated_at: datetime


# ==========================================================
# Service
# ==========================================================


class StockAITradeReviewService:

    """
    Institutional AI post-trade review engine.
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
                    CREATE TABLE IF NOT EXISTS stock_ai_trade_reviews (

                        id BIGSERIAL PRIMARY KEY,

                        order_id BIGINT,

                        position_id BIGINT,

                        symbol VARCHAR(20),

                        side VARCHAR(10),

                        overall_rating DOUBLE PRECISION,

                        execution_rating DOUBLE PRECISION,

                        timing_rating DOUBLE PRECISION,

                        discipline_rating DOUBLE PRECISION,

                        risk_rating DOUBLE PRECISION,

                        confidence DOUBLE PRECISION,

                        summary TEXT,

                        strengths TEXT,

                        weaknesses TEXT,

                        recommendations TEXT,

                        generated_at TIMESTAMP
                    )
                    """
                )

            )

            self.db.commit()

        except SQLAlchemyError:

            logger.exception(
                "Unable to initialize AI review tables."
            )

            try:
                self.db.rollback()
            except Exception:
                pass

    # ======================================================
    # Helpers
    # ======================================================

    @staticmethod
    def _average(*values: float) -> float:

        vals = [v for v in values if v is not None]

        if not vals:
            return 0.0

        return round(sum(vals) / len(vals), 2)

    @staticmethod
    def _grade(score: float) -> str:

        if score >= 95:
            return "Institutional"

        if score >= 85:
            return "Excellent"

        if score >= 75:
            return "Good"

        if score >= 65:
            return "Average"

        if score >= 50:
            return "Needs Improvement"

        return "Poor"

    # ======================================================
    # Public Review API
    # ======================================================

    def review_trade(
        self,
        *,
        attribution: Any,
    ) -> AITradeReview:
        """
        Full review logic continues in Part 2.
        """

        return AITradeReview(

            order_id=getattr(
                attribution,
                "order_id",
                None,
            ),

            position_id=getattr(
                attribution,
                "position_id",
                None,
            ),

            symbol=getattr(
                attribution,
                "symbol",
                "",
            ),

            side=getattr(
                attribution,
                "side",
                "",
            ),

            overall_rating=0.0,

            execution_rating=0.0,

            timing_rating=0.0,

            discipline_rating=0.0,

            risk_rating=0.0,

            confidence=0.0,

            summary="",

            strengths=[],

            weaknesses=[],

            recommendations=[],

            generated_at=datetime.now(UTC),
        )
    # ======================================================
    # AI Review Engine
    # ======================================================

    def review_trade(
        self,
        *,
        attribution: Any,
    ) -> AITradeReview:
        """
        Generate an institutional post-trade review.
        """

        execution_rating = float(
            getattr(
                attribution,
                "execution_score",
                0.0,
            )
        )

        timing_rating = float(
            getattr(
                attribution,
                "timing_score",
                0.0,
            )
        )

        risk_rating = float(
            getattr(
                attribution,
                "risk_score",
                0.0,
            )
        )

        discipline_rating = float(
            getattr(
                attribution,
                "strategy_score",
                0.0,
            )
        )

        overall_rating = self._average(

            execution_rating,

            timing_rating,

            discipline_rating,

            risk_rating,
        )

        confidence = min(

            100.0,

            overall_rating + 5,

        )

        strengths = list(

            getattr(
                attribution,
                "strengths",
                [],
            )

        )

        weaknesses = list(

            getattr(
                attribution,
                "weaknesses",
                [],
            )

        )

        recommendations: List[str] = []

        #
        # Execution
        #

        if execution_rating >= 90:

            recommendations.append(
                "Continue using current execution methodology."
            )

        elif execution_rating >= 75:

            recommendations.append(
                "Reduce execution slippage through improved limit order usage."
            )

        else:

            recommendations.append(
                "Execution quality requires immediate improvement."
            )

        #
        # Timing
        #

        if timing_rating < 80:

            recommendations.append(
                "Improve entry and exit timing."
            )

        #
        # Discipline
        #

        if discipline_rating < 80:

            recommendations.append(
                "Increase adherence to trading plan."
            )

        #
        # Risk
        #

        if risk_rating < 80:

            recommendations.append(
                "Reduce position risk and improve stop placement."
            )

        #
        # Summary
        #

        grade = self._grade(
            overall_rating,
        )

        summary = (

            f"{grade} institutional trade. "

            f"Overall AI score "

            f"{overall_rating:.1f}/100."

        )

        return AITradeReview(

            order_id=getattr(
                attribution,
                "order_id",
                None,
            ),

            position_id=getattr(
                attribution,
                "position_id",
                None,
            ),

            symbol=getattr(
                attribution,
                "symbol",
                "",
            ),

            side=getattr(
                attribution,
                "side",
                "",
            ),

            overall_rating=overall_rating,

            execution_rating=execution_rating,

            timing_rating=timing_rating,

            discipline_rating=discipline_rating,

            risk_rating=risk_rating,

            confidence=confidence,

            summary=summary,

            strengths=strengths,

            weaknesses=weaknesses,

            recommendations=recommendations,

            generated_at=datetime.now(
                UTC,
            ),
        )

    # ======================================================
    # Persistence
    # ======================================================

    def _persist_review(
        self,
        review: AITradeReview,
    ) -> None:

        if self.db is None:
            return

        try:

            self.db.execute(

                text(
                    """
                    INSERT INTO stock_ai_trade_reviews (

                        order_id,
                        position_id,

                        symbol,
                        side,

                        overall_rating,
                        execution_rating,
                        timing_rating,
                        discipline_rating,
                        risk_rating,

                        confidence,

                        summary,

                        strengths,

                        weaknesses,

                        recommendations,

                        generated_at

                    )
                    VALUES (

                        :order_id,
                        :position_id,

                        :symbol,
                        :side,

                        :overall_rating,
                        :execution_rating,
                        :timing_rating,
                        :discipline_rating,
                        :risk_rating,

                        :confidence,

                        :summary,

                        :strengths,

                        :weaknesses,

                        :recommendations,

                        :generated_at
                    )
                    """
                ),

                {

                    "order_id":
                        review.order_id,

                    "position_id":
                        review.position_id,

                    "symbol":
                        review.symbol,

                    "side":
                        review.side,

                    "overall_rating":
                        review.overall_rating,

                    "execution_rating":
                        review.execution_rating,

                    "timing_rating":
                        review.timing_rating,

                    "discipline_rating":
                        review.discipline_rating,

                    "risk_rating":
                        review.risk_rating,

                    "confidence":
                        review.confidence,

                    "summary":
                        review.summary,

                    "strengths":
                        "\n".join(
                            review.strengths,
                        ),

                    "weaknesses":
                        "\n".join(
                            review.weaknesses,
                        ),

                    "recommendations":
                        "\n".join(
                            review.recommendations,
                        ),

                    "generated_at":
                        review.generated_at,
                },

            )

            self.db.commit()

        except SQLAlchemyError:

            logger.exception(
                "Unable to persist AI review."
            )

            try:
                self.db.rollback()
            except Exception:
                pass

    # ======================================================
    # Public API
    # ======================================================

    def generate_review(
            self,
            *,
            attribution: Any,
    ) -> AITradeReview:
        """
        Generates and persists a complete AI trade review.
        """

        review = self.review_trade(
            attribution=attribution,
        )

        self._persist_review(
            review,
        )

        return review

    # ======================================================
    # Query API
    # ======================================================

    def get_reviews(
            self,
            *,
            order_id: Optional[int] = None,
            position_id: Optional[int] = None,
            symbol: Optional[str] = None,
            limit: int = 250,
    ) -> List[Dict[str, Any]]:

        if self.db is None:
            return []

        sql = """
            SELECT *
            FROM stock_ai_trade_reviews
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

                dict(row)

                for row in rows

            ]

        except SQLAlchemyError:

            logger.exception(
                "Unable to load AI trade reviews."
            )

            return []

    # ======================================================
    # Executive Dashboard Summary
    # ======================================================

    def summary(
            self,
    ) -> Dict[str, Any]:

        reviews = self.get_reviews(
            limit=100000,
        )

        if not reviews:
            return {

                "review_count": 0,

                "average_rating": 0.0,

                "average_confidence": 0.0,

                "institutional": 0,

                "excellent": 0,

                "good": 0,

                "average": 0,

                "needs_improvement": 0,

                "poor": 0,
            }

        avg_rating = (

                sum(

                    r["overall_rating"]

                    for r in reviews

                )

                / len(reviews)

        )

        avg_confidence = (

                sum(

                    r["confidence"]

                    for r in reviews

                )

                / len(reviews)

        )

        summary = {

            "review_count":
                len(reviews),

            "average_rating":
                round(
                    avg_rating,
                    2,
                ),

            "average_confidence":
                round(
                    avg_confidence,
                    2,
                ),

            "institutional": 0,

            "excellent": 0,

            "good": 0,

            "average": 0,

            "needs_improvement": 0,

            "poor": 0,
        }

        for row in reviews:

            rating = row["overall_rating"]

            grade = self._grade(
                rating,
            )

            if grade == "Institutional":

                summary["institutional"] += 1

            elif grade == "Excellent":

                summary["excellent"] += 1

            elif grade == "Good":

                summary["good"] += 1

            elif grade == "Average":

                summary["average"] += 1

            elif grade == "Needs Improvement":

                summary["needs_improvement"] += 1

            else:

                summary["poor"] += 1

        return summary

# ==========================================================
# Factory
# ==========================================================

_ai_trade_review_service = None

def get_stock_ai_trade_review_service(
        db,
) -> StockAITradeReviewService:

    global _ai_trade_review_service

    if (

            _ai_trade_review_service is None

            or _ai_trade_review_service.db is not db

    ):
        _ai_trade_review_service = (

            StockAITradeReviewService(
                db,
            )

        )

    return _ai_trade_review_service