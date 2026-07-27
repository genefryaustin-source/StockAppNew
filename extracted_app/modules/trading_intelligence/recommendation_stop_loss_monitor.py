"""
modules/trading_intelligence/recommendation_stop_loss_monitor.py

Recommendation Stop Loss Monitor

Monitors active recommendation positions against
their stop-loss levels and generates escalating
risk alerts.

Responsibilities
----------------
- Distance to stop calculation
- Risk remaining analysis
- Stop breach detection
- Stop proximity alerts
- Drawdown monitoring
- Portfolio stop-risk analytics
- Validation-center integration

Designed to work with:

trade_recommendations
portfolio_positions
recommendation_lifecycle_engine
recommendation_alert_center
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd
from sqlalchemy import text


class RecommendationStopLossMonitor:

    STOP_WARNING_THRESHOLD = 25.0
    STOP_ELEVATED_THRESHOLD = 10.0
    STOP_CRITICAL_THRESHOLD = 5.0

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
    # STOP METRICS
    # =====================================================

    def calculate_distance_to_stop_pct(
        self,
        current_price: float,
        stop_price: float,
    ) -> float:

        try:

            current_price = float(current_price)
            stop_price = float(stop_price)

            if current_price <= 0:
                return 0.0

            return round(
                abs(
                    (
                        current_price - stop_price
                    ) / current_price
                ) * 100.0,
                2,
            )

        except Exception:
            return 0.0

    def calculate_risk_remaining_pct(
        self,
        entry_price: float,
        current_price: float,
        stop_price: float,
    ) -> float:

        try:

            entry_price = float(entry_price)
            current_price = float(current_price)
            stop_price = float(stop_price)

            total_risk = (
                entry_price - stop_price
            )

            if total_risk <= 0:
                return 0.0

            remaining_risk = (
                current_price - stop_price
            )

            pct = (
                remaining_risk
                / total_risk
            ) * 100.0

            return round(
                max(0.0, pct),
                2,
            )

        except Exception:
            return 0.0

    def calculate_drawdown_pct(
        self,
        entry_price: float,
        current_price: float,
    ) -> float:

        try:

            entry_price = float(entry_price)
            current_price = float(current_price)

            if entry_price <= 0:
                return 0.0

            return round(
                (
                    (current_price - entry_price)
                    / entry_price
                ) * 100.0,
                2,
            )

        except Exception:
            return 0.0

    def calculate_risk_dollars_remaining(
        self,
        qty: float,
        current_price: float,
        stop_price: float,
    ) -> float:

        try:

            qty = float(qty)
            current_price = float(current_price)
            stop_price = float(stop_price)

            return round(
                qty *
                max(
                    current_price - stop_price,
                    0.0,
                ),
                2,
            )

        except Exception:
            return 0.0

    # =====================================================
    # STATUS CLASSIFICATION
    # =====================================================

    def determine_stop_status(
        self,
        current_price: float,
        stop_price: float,
    ) -> str:

        try:

            current_price = float(current_price)
            stop_price = float(stop_price)

            if stop_price <= 0:
                return "NO_STOP"

            if current_price <= stop_price:
                return "STOP_BREACHED"

            distance_pct = (
                self.calculate_distance_to_stop_pct(
                    current_price,
                    stop_price,
                )
            )

            if distance_pct <= self.STOP_CRITICAL_THRESHOLD:
                return "CRITICAL"

            if distance_pct <= self.STOP_ELEVATED_THRESHOLD:
                return "ELEVATED"

            if distance_pct <= self.STOP_WARNING_THRESHOLD:
                return "WARNING"

            return "SAFE"

        except Exception:
            return "UNKNOWN"

    # =====================================================
    # MONITOR VIEW
    # =====================================================

    def generate_monitor_view(
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
                or 0.0
            )

            stop_price = float(
                row.get("stop_price")
                or 0.0
            )

            qty = float(
                row.get("qty")
                or 0.0
            )

            distance_pct = (
                self.calculate_distance_to_stop_pct(
                    current_price,
                    stop_price,
                )
            )

            risk_remaining_pct = (
                self.calculate_risk_remaining_pct(
                    entry_price,
                    current_price,
                    stop_price,
                )
            )

            drawdown_pct = (
                self.calculate_drawdown_pct(
                    entry_price,
                    current_price,
                )
            )

            risk_remaining_dollars = (
                self.calculate_risk_dollars_remaining(
                    qty,
                    current_price,
                    stop_price,
                )
            )

            status = self.determine_stop_status(
                current_price,
                stop_price,
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

                "stop_price":
                    stop_price,

                "distance_to_stop_pct":
                    distance_pct,

                "risk_remaining_pct":
                    risk_remaining_pct,

                "drawdown_pct":
                    drawdown_pct,

                "risk_remaining_dollars":
                    risk_remaining_dollars,

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

    def get_stop_alerts(
        self,
        portfolio_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:

        monitor = self.generate_monitor_view(
            portfolio_id
        )

        alerts = []

        if monitor.empty:
            return alerts

        for _, row in monitor.iterrows():

            symbol = str(
                row.get("symbol")
            )

            status = str(
                row.get("status")
            )

            distance = float(
                row.get(
                    "distance_to_stop_pct",
                    0.0,
                )
            )

            if status == "WARNING":

                alerts.append({
                    "symbol": symbol,
                    "severity": "LOW",
                    "alert_type":
                        "STOP_WARNING",
                    "message":
                        f"{symbol} is "
                        f"{distance:.1f}% "
                        f"from stop.",
                })

            elif status == "ELEVATED":

                alerts.append({
                    "symbol": symbol,
                    "severity": "MEDIUM",
                    "alert_type":
                        "STOP_ELEVATED",
                    "message":
                        f"{symbol} is "
                        f"{distance:.1f}% "
                        f"from stop.",
                })

            elif status == "CRITICAL":

                alerts.append({
                    "symbol": symbol,
                    "severity": "HIGH",
                    "alert_type":
                        "STOP_CRITICAL",
                    "message":
                        f"{symbol} is "
                        f"{distance:.1f}% "
                        f"from stop.",
                })

            elif status == "STOP_BREACHED":

                alerts.append({
                    "symbol": symbol,
                    "severity": "CRITICAL",
                    "alert_type":
                        "STOP_BREACHED",
                    "message":
                        f"{symbol} breached "
                        f"its stop-loss.",
                })

        return alerts

    def get_stop_breaches(
        self,
        portfolio_id: Optional[str] = None,
    ) -> pd.DataFrame:

        monitor = self.generate_monitor_view(
            portfolio_id
        )

        if monitor.empty:
            return monitor

        return monitor[
            monitor["status"]
            == "STOP_BREACHED"
        ].copy()

    # =====================================================
    # SUMMARY
    # =====================================================

    def generate_stop_summary(
        self,
        portfolio_id: Optional[str] = None,
    ) -> Dict[str, Any]:

        monitor = self.generate_monitor_view(
            portfolio_id
        )

        if monitor.empty:

            return {
                "positions": 0,
                "stop_breaches": 0,
                "critical": 0,
                "elevated": 0,
                "warning": 0,
                "portfolio_risk_remaining": 0.0,
            }

        return {
            "positions":
                int(len(monitor)),

            "stop_breaches":
                int(
                    (
                        monitor["status"]
                        == "STOP_BREACHED"
                    ).sum()
                ),

            "critical":
                int(
                    (
                        monitor["status"]
                        == "CRITICAL"
                    ).sum()
                ),

            "elevated":
                int(
                    (
                        monitor["status"]
                        == "ELEVATED"
                    ).sum()
                ),

            "warning":
                int(
                    (
                        monitor["status"]
                        == "WARNING"
                    ).sum()
                ),

            "portfolio_risk_remaining":
                round(
                    float(
                        monitor[
                            "risk_remaining_dollars"
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

            monitor = (
                self.generate_monitor_view()
            )

            summary = (
                self.generate_stop_summary()
            )

            alerts = (
                self.get_stop_alerts()
            )

            return {
                "success": True,
                "rows":
                    int(len(monitor)),
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