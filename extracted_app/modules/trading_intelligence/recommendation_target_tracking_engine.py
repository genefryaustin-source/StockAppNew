"""
modules/trading_intelligence/recommendation_target_tracking_engine.py

Recommendation Target Tracking Engine

Tracks active recommendation performance against target prices.

Responsibilities
----------------
- Target progress calculation
- Distance-to-target monitoring
- Target hit detection
- Target approaching alerts
- Reward remaining analysis
- Portfolio-level target statistics
- Validation-center integration

Designed to work with:

trade_recommendations
portfolio_positions
recommendation_lifecycle_engine
recommendation_alert_center
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
from sqlalchemy import text


class RecommendationTargetTrackingEngine:

    TARGET_APPROACHING_THRESHOLD = 0.75
    TARGET_NEAR_THRESHOLD = 0.90
    TARGET_HIT_THRESHOLD = 1.00

    def __init__(self, db):
        self.db = db

    # =====================================================
    # DATA LOADERS
    # =====================================================

    def load_active_positions(
        self,
        portfolio_id: Optional[str] = None,
    ) -> pd.DataFrame:

        sql = """
        SELECT
            p.portfolio_id,
            p.symbol,
            p.qty,
            p.avg_cost,
            p.market_price,
            p.market_value,
            p.unrealized_pnl,

            r.id AS recommendation_id,
            r.created_at,
            r.recommendation,
            r.conviction_score,
            r.confidence_score,
            r.current_price,
            r.entry_price,
            r.stop_price,
            r.target_price,
            r.signal,
            r.sector,
            r.executed

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

    # =====================================================
    # TARGET METRICS
    # =====================================================

    def calculate_progress_to_target(
        self,
        entry_price: float,
        current_price: float,
        target_price: float,
    ) -> float:

        try:

            entry_price = float(entry_price)
            current_price = float(current_price)
            target_price = float(target_price)

            if (
                entry_price <= 0
                or target_price <= entry_price
            ):
                return 0.0

            progress = (
                (current_price - entry_price)
                /
                (target_price - entry_price)
            ) * 100.0

            return round(
                max(0.0, min(progress, 100.0)),
                2,
            )

        except Exception:
            return 0.0

    def calculate_distance_to_target_pct(
        self,
        current_price: float,
        target_price: float,
    ) -> float:

        try:

            current_price = float(current_price)
            target_price = float(target_price)

            if (
                current_price <= 0
                or target_price <= 0
            ):
                return 0.0

            return round(
                (
                    (target_price - current_price)
                    / current_price
                ) * 100.0,
                2,
            )

        except Exception:
            return 0.0

    def calculate_reward_remaining(
        self,
        qty: float,
        current_price: float,
        target_price: float,
    ) -> float:

        try:

            qty = float(qty)
            current_price = float(current_price)
            target_price = float(target_price)

            return round(
                qty *
                (target_price - current_price),
                2,
            )

        except Exception:
            return 0.0

    # =====================================================
    # TARGET STATUS
    # =====================================================

    def determine_target_status(
        self,
        progress_pct: float,
    ) -> str:

        progress_ratio = progress_pct / 100.0

        if progress_ratio >= self.TARGET_HIT_THRESHOLD:
            return "TARGET_HIT"

        if progress_ratio >= self.TARGET_NEAR_THRESHOLD:
            return "TARGET_NEAR"

        if progress_ratio >= self.TARGET_APPROACHING_THRESHOLD:
            return "TARGET_APPROACHING"

        return "IN_PROGRESS"

    # =====================================================
    # TRACKING VIEW
    # =====================================================

    def generate_tracking_view(
        self,
        portfolio_id: Optional[str] = None,
    ) -> pd.DataFrame:

        positions = self.load_active_positions(
            portfolio_id
        )

        if positions.empty:
            return pd.DataFrame()

        rows = []

        for _, row in positions.iterrows():

            entry_price = float(
                row.get("entry_price")
                or row.get("avg_cost")
                or 0.0
            )

            current_price = float(
                row.get("market_price")
                or row.get("current_price")
                or 0.0
            )

            target_price = float(
                row.get("target_price")
                or 0.0
            )

            qty = float(
                row.get("qty")
                or 0.0
            )

            progress_pct = (
                self.calculate_progress_to_target(
                    entry_price,
                    current_price,
                    target_price,
                )
            )

            distance_pct = (
                self.calculate_distance_to_target_pct(
                    current_price,
                    target_price,
                )
            )

            reward_remaining = (
                self.calculate_reward_remaining(
                    qty,
                    current_price,
                    target_price,
                )
            )

            status = self.determine_target_status(
                progress_pct
            )

            rows.append({
                "portfolio_id":
                    row.get("portfolio_id"),

                "recommendation_id":
                    row.get("recommendation_id"),

                "symbol":
                    row.get("symbol"),

                "qty":
                    qty,

                "entry_price":
                    entry_price,

                "current_price":
                    current_price,

                "target_price":
                    target_price,

                "progress_pct":
                    progress_pct,

                "distance_to_target_pct":
                    distance_pct,

                "reward_remaining":
                    reward_remaining,

                "status":
                    status,

                "conviction_score":
                    row.get(
                        "conviction_score"
                    ),

                "confidence_score":
                    row.get(
                        "confidence_score"
                    ),

                "signal":
                    row.get("signal"),

                "sector":
                    row.get("sector"),
            })

        return pd.DataFrame(rows)

    # =====================================================
    # ALERTS
    # =====================================================

    def get_target_alerts(
        self,
        portfolio_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:

        tracking = self.generate_tracking_view(
            portfolio_id
        )

        alerts = []

        if tracking.empty:
            return alerts

        for _, row in tracking.iterrows():

            status = str(
                row.get("status")
            )

            symbol = str(
                row.get("symbol")
            )

            progress = float(
                row.get("progress_pct", 0)
            )

            if status == "TARGET_APPROACHING":

                alerts.append({
                    "symbol": symbol,
                    "severity": "MEDIUM",
                    "alert_type":
                        "TARGET_APPROACHING",
                    "message":
                        f"{symbol} is "
                        f"{progress:.1f}% "
                        f"to target.",
                })

            elif status == "TARGET_NEAR":

                alerts.append({
                    "symbol": symbol,
                    "severity": "HIGH",
                    "alert_type":
                        "TARGET_NEAR",
                    "message":
                        f"{symbol} is "
                        f"{progress:.1f}% "
                        f"to target.",
                })

            elif status == "TARGET_HIT":

                alerts.append({
                    "symbol": symbol,
                    "severity": "CRITICAL",
                    "alert_type":
                        "TARGET_HIT",
                    "message":
                        f"{symbol} reached "
                        f"its target.",
                })

        return alerts

    def get_target_hits(
        self,
        portfolio_id: Optional[str] = None,
    ) -> pd.DataFrame:

        tracking = self.generate_tracking_view(
            portfolio_id)

        if tracking.empty:
            return tracking

        return tracking[
            tracking["status"]
            == "TARGET_HIT"
        ].copy()

    # =====================================================
    # SUMMARY
    # =====================================================

    def generate_target_summary(
        self,
        portfolio_id: Optional[str] = None,
    ) -> Dict[str, Any]:

        tracking = self.generate_tracking_view(
            portfolio_id
        )

        if tracking.empty:

            return {
                "positions": 0,
                "target_hits": 0,
                "approaching": 0,
                "avg_progress_pct": 0.0,
                "reward_remaining": 0.0,
            }

        return {
            "positions":
                int(len(tracking)),

            "target_hits":
                int(
                    (
                        tracking["status"]
                        == "TARGET_HIT"
                    ).sum()
                ),

            "approaching":
                int(
                    tracking["status"]
                    .isin(
                        [
                            "TARGET_APPROACHING",
                            "TARGET_NEAR",
                        ]
                    )
                    .sum()
                ),

            "avg_progress_pct":
                round(
                    float(
                        tracking[
                            "progress_pct"
                        ].mean()
                    ),
                    2,
                ),

            "reward_remaining":
                round(
                    float(
                        tracking[
                            "reward_remaining"
                        ].sum()
                    ),
                    2,
                ),
        }

    # =====================================================
    # VALIDATION
    # =====================================================

    def self_test(self) -> Dict[str, Any]:

        try:

            tracking = (
                self.generate_tracking_view()
            )

            summary = (
                self.generate_target_summary()
            )

            alerts = (
                self.get_target_alerts()
            )

            return {
                "success": True,
                "rows":
                    int(len(tracking)),
                "alerts":
                    len(alerts),
                "summary":
                    summary,
            }

        except Exception as exc:

            return {
                "success": False,
                "error": str(exc),
            }