from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List, Any

import pandas as pd
from sqlalchemy import text


@dataclass
class RecommendationPerformanceSummary:
    total_recommendations: int
    executed_recommendations: int
    execution_rate: float

    total_closed_trades: int
    winning_trades: int
    losing_trades: int

    win_rate: float

    avg_return_pct: float
    avg_net_pnl: float

    total_net_pnl: float

    def to_dict(self):
        return asdict(self)


class RecommendationPerformanceEngine:

    def __init__(self, db):
        self.db = db

    # =====================================================
    # PUBLIC API
    # =====================================================

    def build_summary(
        self,
        portfolio_id: str,
    ) -> RecommendationPerformanceSummary:

        rec_df = self._load_recommendations(
            portfolio_id
        )

        closed_df = self._load_closed_trades(
            portfolio_id
        )

        total_recs = len(rec_df)

        executed_recs = len(
            rec_df[
                rec_df["executed"] == True
            ]
        ) if not rec_df.empty else 0

        execution_rate = (
            executed_recs / total_recs * 100
            if total_recs > 0 else 0
        )

        total_closed = len(closed_df)

        winning = len(
            closed_df[
                closed_df["net_pnl"] > 0
            ]
        ) if not closed_df.empty else 0

        losing = len(
            closed_df[
                closed_df["net_pnl"] <= 0
            ]
        ) if not closed_df.empty else 0

        win_rate = (
            winning / total_closed * 100
            if total_closed > 0 else 0
        )

        avg_return_pct = (
            closed_df["return_pct"].mean()
            if not closed_df.empty
            else 0
        )

        avg_net_pnl = (
            closed_df["net_pnl"].mean()
            if not closed_df.empty
            else 0
        )

        total_net_pnl = (
            closed_df["net_pnl"].sum()
            if not closed_df.empty
            else 0
        )

        return RecommendationPerformanceSummary(
            total_recommendations=total_recs,
            executed_recommendations=executed_recs,
            execution_rate=round(execution_rate, 2),

            total_closed_trades=total_closed,
            winning_trades=winning,
            losing_trades=losing,

            win_rate=round(win_rate, 2),

            avg_return_pct=round(
                avg_return_pct or 0,
                2,
            ),

            avg_net_pnl=round(
                avg_net_pnl or 0,
                2,
            ),

            total_net_pnl=round(
                total_net_pnl or 0,
                2,
            ),
        )

    def recommendation_breakdown(
        self,
        portfolio_id: str,
    ) -> pd.DataFrame:

        sql = text("""
            SELECT
                recommendation,
                COUNT(*) AS recommendation_count,
                AVG(conviction_score) AS avg_conviction,
                AVG(confidence_score) AS avg_confidence
            FROM trade_recommendations
            WHERE portfolio_id = :pid
            GROUP BY recommendation
            ORDER BY recommendation_count DESC
        """)

        return pd.read_sql(
            sql,
            self.db.bind,
            params={"pid": portfolio_id},
        )

    def conviction_analysis(
        self,
        portfolio_id: str,
    ) -> pd.DataFrame:

        sql = text("""
            SELECT
                symbol,
                recommendation,
                conviction_score,
                confidence_score,
                risk_reward,
                executed
            FROM trade_recommendations
            WHERE portfolio_id = :pid
            ORDER BY conviction_score DESC
        """)

        return pd.read_sql(
            sql,
            self.db.bind,
            params={"pid": portfolio_id},
        )

    def signal_effectiveness(
        self,
        portfolio_id: str,
    ) -> pd.DataFrame:

        sql = text("""
            SELECT
                signal,
                COUNT(*) AS signal_count,
                AVG(conviction_score) AS avg_conviction,
                AVG(confidence_score) AS avg_confidence
            FROM trade_recommendations
            WHERE portfolio_id = :pid
              AND signal IS NOT NULL
            GROUP BY signal
            ORDER BY signal_count DESC
        """)

        return pd.read_sql(
            sql,
            self.db.bind,
            params={"pid": portfolio_id},
        )

    def sector_analysis(
        self,
        portfolio_id: str,
    ) -> pd.DataFrame:

        sql = text("""
            SELECT
                sector,
                COUNT(*) AS recommendation_count,
                AVG(conviction_score) AS avg_conviction,
                AVG(confidence_score) AS avg_confidence
            FROM trade_recommendations
            WHERE portfolio_id = :pid
              AND sector IS NOT NULL
            GROUP BY sector
            ORDER BY recommendation_count DESC
        """)

        return pd.read_sql(
            sql,
            self.db.bind,
            params={"pid": portfolio_id},
        )

    # =====================================================
    # DATA ACCESS
    # =====================================================

    def _load_recommendations(
        self,
        portfolio_id: str,
    ) -> pd.DataFrame:

        sql = text("""
            SELECT *
            FROM trade_recommendations
            WHERE portfolio_id = :pid
        """)

        return pd.read_sql(
            sql,
            self.db.bind,
            params={"pid": portfolio_id},
        )

    def _load_closed_trades(
        self,
        portfolio_id: str,
    ) -> pd.DataFrame:

        sql = text("""
            SELECT
                *,
                CASE
                    WHEN entry_price > 0
                    THEN (
                        (exit_price - entry_price)
                        / entry_price
                    ) * 100
                    ELSE 0
                END AS return_pct
            FROM closed_trades
            WHERE portfolio_id = :pid
        """)

        return pd.read_sql(
            sql,
            self.db.bind,
            params={"pid": portfolio_id},
        )