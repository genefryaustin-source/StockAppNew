from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from modules.trading_intelligence.recommendation_command_center import (
    RecommendationCommandCenter,
)
from modules.trading_intelligence.recommendation_target_tracking_engine import (
    RecommendationTargetTrackingEngine,
)
from modules.trading_intelligence.recommendation_stop_loss_monitor import (
    RecommendationStopLossMonitor,
)
from modules.trading_intelligence.portfolio_risk_monitor import (
    PortfolioRiskMonitor,
)


@dataclass
class AutopilotAction:
    symbol: str
    portfolio_id: Optional[str]
    action_type: str
    priority: str
    confidence: float
    title: str
    rationale: str
    suggested_action: str
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class RecommendationAutopilotEngine:
    """
    Recommendation Autopilot Engine

    Converts recommendation lifecycle, target, stop, alert, and
    portfolio-risk signals into suggested trade-management actions.

    This engine does NOT execute trades automatically.
    It recommends operational actions for review.
    """

    PRIORITY_RANK = {
        "CRITICAL": 0,
        "HIGH": 1,
        "MEDIUM": 2,
        "LOW": 3,
        "INFO": 4,
    }

    def __init__(self, db):
        self.db = db
        self.command_center = RecommendationCommandCenter(db)
        self.targets = RecommendationTargetTrackingEngine(db)
        self.stops = RecommendationStopLossMonitor(db)
        self.risk = PortfolioRiskMonitor(db)

    def generate_actions(
        self,
        portfolio_id: Optional[str] = None,
    ) -> pd.DataFrame:
        actions: List[AutopilotAction] = []

        actions.extend(self._target_actions(portfolio_id))
        actions.extend(self._stop_actions(portfolio_id))
        actions.extend(self._risk_actions(portfolio_id))
        actions.extend(self._alert_actions(portfolio_id))

        deduped = self._dedupe(actions)

        rows = [a.to_dict() for a in deduped]
        df = pd.DataFrame(rows)

        if df.empty:
            return df

        df["priority_rank"] = df["priority"].map(
            lambda x: self.PRIORITY_RANK.get(str(x).upper(), 99)
        )

        return (
            df.sort_values(
                ["priority_rank", "confidence", "created_at"],
                ascending=[True, False, False],
            )
            .drop(columns=["priority_rank"])
            .reset_index(drop=True)
        )

    def build_autopilot_summary(
        self,
        portfolio_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        actions = self.generate_actions(portfolio_id)

        if actions.empty:
            return {
                "actions": 0,
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
                "top_action": "None",
                "autopilot_status": "Clear",
            }

        priority = actions["priority"].fillna("INFO").astype(str).str.upper()

        critical = int((priority == "CRITICAL").sum())
        high = int((priority == "HIGH").sum())
        medium = int((priority == "MEDIUM").sum())
        low = int((priority == "LOW").sum())

        if critical > 0:
            status = "Critical Review Required"
        elif high > 0:
            status = "Action Recommended"
        elif medium > 0:
            status = "Monitor Closely"
        else:
            status = "Clear"

        return {
            "actions": int(len(actions)),
            "critical": critical,
            "high": high,
            "medium": medium,
            "low": low,
            "top_action": str(actions.iloc[0]["title"]),
            "autopilot_status": status,
        }

    def _target_actions(
        self,
        portfolio_id: Optional[str],
    ) -> List[AutopilotAction]:
        actions: List[AutopilotAction] = []

        try:
            tracking = self.targets.generate_tracking_view(portfolio_id)
        except Exception:
            return actions

        if tracking.empty:
            return actions

        for _, row in tracking.iterrows():
            symbol = str(row.get("symbol", "")).upper()
            status = str(row.get("status", "")).upper()
            progress = float(row.get("progress_pct") or 0.0)
            reward_remaining = float(row.get("reward_remaining") or 0.0)

            if status == "TARGET_HIT":
                actions.append(
                    AutopilotAction(
                        symbol=symbol,
                        portfolio_id=row.get("portfolio_id"),
                        action_type="TAKE_PROFIT",
                        priority="HIGH",
                        confidence=95.0,
                        title=f"{symbol}: Target Hit",
                        rationale=(
                            f"{symbol} has reached or exceeded its recommendation target. "
                            f"Remaining modeled reward is ${reward_remaining:,.2f}."
                        ),
                        suggested_action="Review position for full or partial profit-taking.",
                        created_at=datetime.utcnow().isoformat(),
                    )
                )

            elif status == "TARGET_NEAR":
                actions.append(
                    AutopilotAction(
                        symbol=symbol,
                        portfolio_id=row.get("portfolio_id"),
                        action_type="PREPARE_PROFIT_TAKE",
                        priority="MEDIUM",
                        confidence=85.0,
                        title=f"{symbol}: Near Target",
                        rationale=f"{symbol} is {progress:.1f}% of the way to target.",
                        suggested_action="Consider raising stop or preparing partial exit.",
                        created_at=datetime.utcnow().isoformat(),
                    )
                )

            elif status == "TARGET_APPROACHING":
                actions.append(
                    AutopilotAction(
                        symbol=symbol,
                        portfolio_id=row.get("portfolio_id"),
                        action_type="MONITOR_TARGET_PROGRESS",
                        priority="LOW",
                        confidence=75.0,
                        title=f"{symbol}: Approaching Target",
                        rationale=f"{symbol} is {progress:.1f}% of the way to target.",
                        suggested_action="Monitor for target continuation and risk/reward compression.",
                        created_at=datetime.utcnow().isoformat(),
                    )
                )

        return actions

    def _stop_actions(
        self,
        portfolio_id: Optional[str],
    ) -> List[AutopilotAction]:
        actions: List[AutopilotAction] = []

        try:
            monitor = self.stops.generate_monitor_view(portfolio_id)
        except Exception:
            return actions

        if monitor.empty:
            return actions

        for _, row in monitor.iterrows():
            symbol = str(row.get("symbol", "")).upper()
            status = str(row.get("status", "")).upper()
            distance = float(row.get("distance_to_stop_pct") or 0.0)
            drawdown = float(row.get("drawdown_pct") or 0.0)

            if status == "STOP_BREACHED":
                actions.append(
                    AutopilotAction(
                        symbol=symbol,
                        portfolio_id=row.get("portfolio_id"),
                        action_type="STOP_EXIT_REVIEW",
                        priority="CRITICAL",
                        confidence=98.0,
                        title=f"{symbol}: Stop Breached",
                        rationale=(
                            f"{symbol} has breached the recommendation stop. "
                            f"Current drawdown from entry is {drawdown:.2f}%."
                        ),
                        suggested_action="Review immediate exit or risk override.",
                        created_at=datetime.utcnow().isoformat(),
                    )
                )

            elif status == "CRITICAL":
                actions.append(
                    AutopilotAction(
                        symbol=symbol,
                        portfolio_id=row.get("portfolio_id"),
                        action_type="STOP_PROXIMITY_CRITICAL",
                        priority="HIGH",
                        confidence=92.0,
                        title=f"{symbol}: Very Close To Stop",
                        rationale=f"{symbol} is only {distance:.2f}% from stop.",
                        suggested_action="Review position immediately; consider reducing exposure.",
                        created_at=datetime.utcnow().isoformat(),
                    )
                )

            elif status == "ELEVATED":
                actions.append(
                    AutopilotAction(
                        symbol=symbol,
                        portfolio_id=row.get("portfolio_id"),
                        action_type="STOP_PROXIMITY_ELEVATED",
                        priority="MEDIUM",
                        confidence=82.0,
                        title=f"{symbol}: Elevated Stop Risk",
                        rationale=f"{symbol} is {distance:.2f}% from stop.",
                        suggested_action="Monitor closely and verify thesis remains intact.",
                        created_at=datetime.utcnow().isoformat(),
                    )
                )

            elif status == "WARNING":
                actions.append(
                    AutopilotAction(
                        symbol=symbol,
                        portfolio_id=row.get("portfolio_id"),
                        action_type="STOP_PROXIMITY_WARNING",
                        priority="LOW",
                        confidence=70.0,
                        title=f"{symbol}: Stop Risk Warning",
                        rationale=f"{symbol} is {distance:.2f}% from stop.",
                        suggested_action="Watch for further downside pressure.",
                        created_at=datetime.utcnow().isoformat(),
                    )
                )

        return actions

    def _risk_actions(
        self,
        portfolio_id: Optional[str],
    ) -> List[AutopilotAction]:
        actions: List[AutopilotAction] = []

        if not portfolio_id:
            return actions

        try:
            summary = self.risk.build_summary(portfolio_id)
            breaches = self.risk.concentration_breaches(portfolio_id)
        except Exception:
            return actions

        if summary.risk_status == "High Risk":
            actions.append(
                AutopilotAction(
                    symbol="PORTFOLIO",
                    portfolio_id=portfolio_id,
                    action_type="PORTFOLIO_RISK_REVIEW",
                    priority="HIGH",
                    confidence=90.0,
                    title="Portfolio Risk Elevated",
                    rationale=(
                        f"Portfolio risk status is High Risk. "
                        f"Largest position is {summary.largest_position_symbol} "
                        f"at {summary.largest_position_pct:.2f}%."
                    ),
                    suggested_action="Review concentration, sizing, and open stop exposure.",
                    created_at=datetime.utcnow().isoformat(),
                )
            )

        if breaches is not None and not breaches.empty:
            for _, row in breaches.iterrows():
                actions.append(
                    AutopilotAction(
                        symbol=str(row.get("symbol_or_sector", "PORTFOLIO"))[:20],
                        portfolio_id=portfolio_id,
                        action_type=str(row.get("breach_type", "RISK_BREACH")),
                        priority=str(row.get("severity", "MEDIUM")).upper(),
                        confidence=88.0,
                        title=f"{row.get('symbol_or_sector')} Concentration Breach",
                        rationale=str(row.get("message", "")),
                        suggested_action="Review position or sector exposure limits.",
                        created_at=datetime.utcnow().isoformat(),
                    )
                )

        return actions

    def _alert_actions(
        self,
        portfolio_id: Optional[str],
    ) -> List[AutopilotAction]:
        actions: List[AutopilotAction] = []

        try:
            alerts = self.command_center.alerts.get_active_alerts(
                portfolio_id=portfolio_id,
                persist=False,
            )
        except Exception:
            return actions

        if alerts.empty:
            return actions

        for _, row in alerts.iterrows():
            severity = str(row.get("severity", "INFO")).upper()
            alert_type = str(row.get("alert_type", "ALERT")).upper()
            symbol = str(row.get("symbol", "PORTFOLIO")).upper()

            if severity not in {"CRITICAL", "HIGH"}:
                continue

            actions.append(
                AutopilotAction(
                    symbol=symbol,
                    portfolio_id=row.get("portfolio_id"),
                    action_type=f"ALERT_REVIEW_{alert_type}",
                    priority=severity,
                    confidence=86.0,
                    title=f"{symbol}: {alert_type}",
                    rationale=str(row.get("message", "")),
                    suggested_action="Review alert and decide whether action is required.",
                    created_at=datetime.utcnow().isoformat(),
                )
            )

        return actions

    def _dedupe(
        self,
        actions: List[AutopilotAction],
    ) -> List[AutopilotAction]:
        seen = set()
        out: List[AutopilotAction] = []

        for action in actions:
            key = (
                action.portfolio_id,
                action.symbol,
                action.action_type,
            )

            if key in seen:
                continue

            seen.add(key)
            out.append(action)

        return out

    def self_test(
        self,
        portfolio_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            actions = self.generate_actions(portfolio_id)
            summary = self.build_autopilot_summary(portfolio_id)

            return {
                "success": True,
                "actions": int(len(actions)),
                "summary": summary,
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