from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

import pandas as pd

from modules.trading_intelligence.recommendation_lifecycle_engine import RecommendationLifecycleEngine
from modules.trading_intelligence.recommendation_target_tracking_engine import RecommendationTargetTrackingEngine
from modules.trading_intelligence.recommendation_stop_loss_monitor import RecommendationStopLossMonitor
from modules.trading_intelligence.recommendation_alert_center import RecommendationAlertCenter
from modules.trading_intelligence.trade_management_engine import TradeManagementEngine
from modules.trading_intelligence.recommendation_performance_engine import RecommendationPerformanceEngine
from modules.trading_intelligence.trade_attribution_engine import TradeAttributionEngine
from modules.trading_intelligence.portfolio_risk_monitor import PortfolioRiskMonitor


class RecommendationCommandCenter:
    """
    Institutional recommendation operations control tower.

    Combines:
    - Lifecycle
    - Alerts
    - Target Tracking
    - Stop Monitoring
    - Trade Management
    - Performance
    - Attribution
    - Portfolio Risk
    """

    def __init__(self, db):
        self.db = db
        self.lifecycle = RecommendationLifecycleEngine(db)
        self.targets = RecommendationTargetTrackingEngine(db)
        self.stops = RecommendationStopLossMonitor(db)
        self.alerts = RecommendationAlertCenter(db)
        self.trade_management = TradeManagementEngine(db)
        self.performance = RecommendationPerformanceEngine(db)
        self.attribution = TradeAttributionEngine(db)
        self.risk = PortfolioRiskMonitor(db)

    def build_command_snapshot(
        self,
        portfolio_id: Optional[str] = None,
        persist_alerts: bool = False,
    ) -> Dict[str, Any]:
        self.alerts.ensure_schema()

        lifecycle_summary = self.lifecycle.generate_lifecycle_summary(portfolio_id)
        lifecycle_metrics = self.lifecycle.recommendation_funnel_metrics(portfolio_id)

        target_summary = self.targets.generate_target_summary(portfolio_id)
        stop_summary = self.stops.generate_stop_summary(portfolio_id)

        alert_df = self.alerts.get_active_alerts(
            portfolio_id=portfolio_id,
            persist=persist_alerts,
        )
        alert_counts = self.alerts.get_alert_counts(portfolio_id)

        performance_summary = self.performance.build_summary(portfolio_id).to_dict()
        attribution_summary = self.attribution.build_summary(portfolio_id).to_dict()
        risk_summary = self.risk.build_summary(portfolio_id).to_dict()

        trade_metrics = (
            self.trade_management.get_summary_metrics(portfolio_id)
            if portfolio_id
            else {}
        )

        return {
            "generated_at": datetime.utcnow().isoformat(),
            "portfolio_id": portfolio_id,
            "lifecycle_summary": lifecycle_summary,
            "lifecycle_metrics": lifecycle_metrics,
            "target_summary": target_summary,
            "stop_summary": stop_summary,
            "alert_counts": alert_counts,
            "active_alerts": int(len(alert_df)),
            "performance_summary": performance_summary,
            "attribution_summary": attribution_summary,
            "risk_summary": risk_summary,
            "trade_management_summary": trade_metrics,
        }

    def build_health_score(
        self,
        portfolio_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        snapshot = self.build_command_snapshot(
            portfolio_id=portfolio_id,
            persist_alerts=False,
        )

        score = 100.0
        reasons = []

        alerts = snapshot.get("alert_counts", {})
        critical = int(alerts.get("critical", 0))
        high = int(alerts.get("high", 0))
        medium = int(alerts.get("medium", 0))

        if critical:
            score -= critical * 20
            reasons.append(f"{critical} critical alerts")

        if high:
            score -= high * 10
            reasons.append(f"{high} high severity alerts")

        if medium:
            score -= medium * 5
            reasons.append(f"{medium} medium severity alerts")

        risk_status = (
            snapshot
            .get("risk_summary", {})
            .get("risk_status", "")
        )

        if risk_status == "High Risk":
            score -= 20
            reasons.append("portfolio risk is high")
        elif risk_status == "Moderate Risk":
            score -= 10
            reasons.append("portfolio risk is moderate")

        stop_summary = snapshot.get("stop_summary", {})
        if int(stop_summary.get("stop_breaches", 0)) > 0:
            score -= 25
            reasons.append("stop-loss breach detected")

        target_summary = snapshot.get("target_summary", {})
        if int(target_summary.get("target_hits", 0)) > 0:
            reasons.append("target hit available for review")

        score = max(0.0, min(100.0, score))

        if score >= 85:
            status = "Healthy"
        elif score >= 65:
            status = "Watch"
        elif score >= 40:
            status = "At Risk"
        else:
            status = "Critical"

        return {
            "score": round(score, 2),
            "status": status,
            "reasons": reasons,
            "generated_at": datetime.utcnow().isoformat(),
        }

    def load_all_views(
        self,
        portfolio_id: Optional[str] = None,
    ) -> Dict[str, pd.DataFrame]:
        return {
            "lifecycle": self.lifecycle.generate_lifecycle_view(portfolio_id),
            "targets": self.targets.generate_tracking_view(portfolio_id),
            "stops": self.stops.generate_monitor_view(portfolio_id),
            "alerts": self.alerts.get_active_alerts(portfolio_id, persist=False),
            "trade_management": (
                self.trade_management.get_trade_management_dataframe(portfolio_id)
                if portfolio_id
                else pd.DataFrame()
            ),
            "attribution": self.attribution.load_attribution_table(portfolio_id),
            "risk_positions": self.risk.load_positions(portfolio_id),
            "sector_risk": self.risk.sector_exposure(portfolio_id),
        }

    def self_test(
        self,
        portfolio_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            snapshot = self.build_command_snapshot(
                portfolio_id=portfolio_id,
                persist_alerts=False,
            )
            health = self.build_health_score(portfolio_id)
            views = self.load_all_views(portfolio_id)

            return {
                "success": True,
                "snapshot_keys": list(snapshot.keys()),
                "health": health,
                "view_rows": {
                    name: int(len(df))
                    for name, df in views.items()
                },
            }

        except Exception as exc:
            try:
                self.db.rollback()
            except Exception:
                pass

            return {
                "success": False,
                "error": str(exc),
            }