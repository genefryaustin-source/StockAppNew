"""
modules/trading_intelligence/recommendation_lifecycle_engine.py

Recommendation Lifecycle Engine

Tracks recommendations from creation through execution,
target progression, stop monitoring, closure, expiration,
and portfolio attribution.

Lifecycle States

OPEN
EXECUTED
TARGET_APPROACHING
TARGET_HIT
STOP_APPROACHING
STOP_HIT
CLOSED_WIN
CLOSED_LOSS
EXPIRED
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

import pandas as pd
from sqlalchemy import text


class RecommendationLifecycleEngine:

    LIFECYCLE_OPEN = "OPEN"
    LIFECYCLE_EXECUTED = "EXECUTED"
    LIFECYCLE_TARGET_APPROACHING = "TARGET_APPROACHING"
    LIFECYCLE_TARGET_HIT = "TARGET_HIT"
    LIFECYCLE_STOP_APPROACHING = "STOP_APPROACHING"
    LIFECYCLE_STOP_HIT = "STOP_HIT"
    LIFECYCLE_CLOSED_WIN = "CLOSED_WIN"
    LIFECYCLE_CLOSED_LOSS = "CLOSED_LOSS"
    LIFECYCLE_EXPIRED = "EXPIRED"

    DEFAULT_EXPIRATION_DAYS = 30

    def __init__(self, db):
        self.db = db

    # =====================================================
    # RECOMMENDATION LOADERS
    # =====================================================

    def get_all_recommendations(
        self,
        portfolio_id: Optional[str] = None,
    ) -> pd.DataFrame:

        sql = """
        SELECT *
        FROM trade_recommendations
        WHERE 1=1
        """

        params = {}

        if portfolio_id:
            sql += """
            AND portfolio_id = :portfolio_id
            """
            params["portfolio_id"] = portfolio_id

        sql += """
        ORDER BY created_at DESC
        """

        return pd.read_sql(
            text(sql),
            self.db.bind,
            params=params,
        )

    def get_active_recommendations(
        self,
        portfolio_id: Optional[str] = None,
    ) -> pd.DataFrame:

        df = self.get_all_recommendations(portfolio_id)

        if df.empty:
            return df

        return df[
            (
                df["status"]
                .fillna("open")
                .astype(str)
                .str.lower()
                != "closed"
            )
        ].copy()

    def get_executed_recommendations(
        self,
        portfolio_id: Optional[str] = None,
    ) -> pd.DataFrame:

        df = self.get_all_recommendations(portfolio_id)

        if df.empty:
            return df

        return df[df["executed"] == True].copy()

    def get_open_positions_from_recommendations(
        self,
        portfolio_id: Optional[str] = None,
    ) -> pd.DataFrame:

        sql = """
        SELECT
            p.*,
            r.id AS recommendation_id,
            r.created_at AS recommendation_created_at,
            r.conviction_score,
            r.confidence_score,
            r.target_price,
            r.stop_price,
            r.signal,
            r.recommendation
        FROM portfolio_positions p
        LEFT JOIN trade_recommendations r
            ON p.symbol = r.symbol
        WHERE p.qty > 0
        """

        params = {}

        if portfolio_id:
            sql += """
            AND p.portfolio_id = :portfolio_id
            """
            params["portfolio_id"] = portfolio_id

        return pd.read_sql(
            text(sql),
            self.db.bind,
            params=params,
        )

    def get_closed_recommendations(
        self,
        portfolio_id: Optional[str] = None,
    ) -> pd.DataFrame:

        sql = """
        SELECT
            ct.*,
            tr.id AS recommendation_id
        FROM closed_trades ct
        LEFT JOIN trade_recommendations tr
            ON ct.symbol = tr.symbol
        WHERE 1=1
        """

        params = {}

        if portfolio_id:
            sql += """
            AND ct.portfolio_id = :portfolio_id
            """
            params["portfolio_id"] = portfolio_id

        return pd.read_sql(
            text(sql),
            self.db.bind,
            params=params,
        )

    # =====================================================
    # AGE CALCULATIONS
    # =====================================================

    def calculate_recommendation_age(
        self,
        recommendation: Dict[str, Any],
    ) -> float:

        created_at = recommendation.get("created_at")

        if not created_at:
            return 0.0

        if isinstance(created_at, str):
            created_at = pd.to_datetime(created_at)

        return (
            datetime.utcnow() - created_at.replace(tzinfo=None)
        ).total_seconds() / 86400.0

    def calculate_days_since_execution(
        self,
        recommendation: Dict[str, Any],
    ) -> float:

        executed_at = recommendation.get("executed_at")

        if not executed_at:
            return 0.0

        if isinstance(executed_at, str):
            executed_at = pd.to_datetime(executed_at)

        return (
            datetime.utcnow() - executed_at.replace(tzinfo=None)
        ).total_seconds() / 86400.0

    # =====================================================
    # LIFECYCLE STATUS
    # =====================================================

    def determine_lifecycle_status(
        self,
        recommendation: Dict[str, Any],
        current_price: Optional[float] = None,
        position_open: bool = False,
    ) -> str:

        executed = bool(
            recommendation.get("executed", False)
        )

        target_price = float(
            recommendation.get("target_price") or 0.0
        )

        stop_price = float(
            recommendation.get("stop_price") or 0.0
        )

        age_days = self.calculate_recommendation_age(
            recommendation
        )

        if age_days > self.DEFAULT_EXPIRATION_DAYS:
            return self.LIFECYCLE_EXPIRED

        if not executed:
            return self.LIFECYCLE_OPEN

        if not position_open:
            return self.LIFECYCLE_EXECUTED

        if current_price and target_price > 0:

            progress = current_price / target_price

            if progress >= 1.00:
                return self.LIFECYCLE_TARGET_HIT

            if progress >= 0.90:
                return self.LIFECYCLE_TARGET_APPROACHING

        if current_price and stop_price > 0:

            stop_distance = abs(
                current_price - stop_price
            )

            pct_distance = (
                stop_distance / current_price
            )

            if current_price <= stop_price:
                return self.LIFECYCLE_STOP_HIT

            if pct_distance <= 0.05:
                return self.LIFECYCLE_STOP_APPROACHING

        return self.LIFECYCLE_EXECUTED

    # =====================================================
    # PORTFOLIO LIFECYCLE VIEW
    # =====================================================

    def generate_lifecycle_view(
        self,
        portfolio_id: Optional[str] = None,
    ) -> pd.DataFrame:

        recs = self.get_all_recommendations(
            portfolio_id
        )

        positions = self.get_open_positions_from_recommendations(
            portfolio_id
        )

        position_lookup = {}

        if not positions.empty:

            for _, row in positions.iterrows():

                position_lookup[
                    str(row["symbol"]).upper()
                ] = row

        rows = []

        for _, rec in recs.iterrows():

            symbol = str(
                rec.get("symbol", "")
            ).upper()

            position = position_lookup.get(symbol)

            position_open = position is not None

            current_price = None

            if position is not None:
                current_price = float(
                    position.get("market_price") or 0
                )

            lifecycle = self.determine_lifecycle_status(
                recommendation=rec.to_dict(),
                current_price=current_price,
                position_open=position_open,
            )

            rows.append({
                "symbol": symbol,
                "recommendation": rec.get(
                    "recommendation"
                ),
                "created_at": rec.get(
                    "created_at"
                ),
                "executed": rec.get(
                    "executed"
                ),
                "status": lifecycle,
                "age_days":
                    self.calculate_recommendation_age(
                        rec.to_dict()
                    ),
                "conviction_score":
                    rec.get(
                        "conviction_score"
                    ),
                "confidence_score":
                    rec.get(
                        "confidence_score"
                    ),
                "target_price":
                    rec.get(
                        "target_price"
                    ),
                "stop_price":
                    rec.get(
                        "stop_price"
                    ),
                "current_price":
                    current_price,
            })

        return pd.DataFrame(rows)

    # =====================================================
    # SUMMARY METRICS
    # =====================================================

    def recommendation_funnel_metrics(
        self,
        portfolio_id: Optional[str] = None,
    ) -> Dict[str, Any]:

        recs = self.get_all_recommendations(
            portfolio_id
        )

        if recs.empty:

            return {
                "total": 0,
                "executed": 0,
                "open": 0,
                "expired": 0,
                "execution_rate": 0.0,
            }

        lifecycle = self.generate_lifecycle_view(
            portfolio_id
        )

        total = len(recs)

        executed = int(
            recs["executed"]
            .fillna(False)
            .sum()
        )

        open_count = int(
            (
                lifecycle["status"]
                == self.LIFECYCLE_OPEN
            ).sum()
        )

        expired = int(
            (
                lifecycle["status"]
                == self.LIFECYCLE_EXPIRED
            ).sum()
        )

        return {
            "total": total,
            "executed": executed,
            "open": open_count,
            "expired": expired,
            "execution_rate":
                round(
                    (executed / total) * 100,
                    2,
                )
                if total > 0
                else 0.0,
        }

    def generate_lifecycle_summary(
        self,
        portfolio_id: Optional[str] = None,
    ) -> Dict[str, Any]:

        lifecycle = self.generate_lifecycle_view(
            portfolio_id
        )

        if lifecycle.empty:

            return {
                "total": 0,
                "status_counts": {},
            }

        status_counts = (
            lifecycle["status"]
            .value_counts()
            .to_dict()
        )

        return {
            "total":
                int(len(lifecycle)),
            "status_counts":
                status_counts,
            "generated_at":
                datetime.utcnow().isoformat(),
        }

    # =====================================================
    # VALIDATION
    # =====================================================

    def self_test(self) -> Dict[str, Any]:

        try:

            lifecycle = (
                self.generate_lifecycle_view()
            )

            metrics = (
                self.recommendation_funnel_metrics()
            )

            summary = (
                self.generate_lifecycle_summary()
            )

            return {
                "success": True,
                "rows":
                    int(len(lifecycle)),
                "metrics":
                    metrics,
                "summary":
                    summary,
            }

        except Exception as exc:

            return {
                "success": False,
                "error": str(exc),
            }