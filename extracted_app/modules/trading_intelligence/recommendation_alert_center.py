"""
modules/trading_intelligence/recommendation_alert_center.py
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
from sqlalchemy import text

from modules.trading_intelligence.recommendation_lifecycle_engine import (
    RecommendationLifecycleEngine,
)
from modules.trading_intelligence.recommendation_target_tracking_engine import (
    RecommendationTargetTrackingEngine,
)
from modules.trading_intelligence.recommendation_stop_loss_monitor import (
    RecommendationStopLossMonitor,
)
from modules.trading_intelligence.trade_management_engine import (
    TradeManagementEngine,
)
from modules.trading_intelligence.portfolio_risk_monitor import (
    PortfolioRiskMonitor,
)


@dataclass
class RecommendationAlert:
    symbol: str
    portfolio_id: Optional[str]
    alert_type: str
    severity: str
    title: str
    message: str
    source: str
    recommendation_id: Optional[int] = None
    created_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        out = asdict(self)
        if out.get("created_at") is None:
            out["created_at"] = datetime.utcnow()
        return out


class RecommendationAlertCenter:
    SEVERITY_ORDER = {
        "CRITICAL": 0,
        "HIGH": 1,
        "MEDIUM": 2,
        "LOW": 3,
        "INFO": 4,
    }

    def __init__(self, db):
        self.db = db
        self.lifecycle_engine = RecommendationLifecycleEngine(db)
        self.target_engine = RecommendationTargetTrackingEngine(db)
        self.stop_engine = RecommendationStopLossMonitor(db)
        self.trade_management_engine = TradeManagementEngine(db)
        self.portfolio_risk_monitor = PortfolioRiskMonitor(db)

    def _rollback_safe(self) -> None:
        try:
            self.db.rollback()
        except Exception:
            pass

    def ensure_schema(self) -> None:
        self._rollback_safe()

        try:
            self.db.execute(text("""
                CREATE TABLE IF NOT EXISTS recommendation_alerts (
                    id SERIAL PRIMARY KEY,
                    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    recommendation_id INTEGER,
                    portfolio_id VARCHAR(36),
                    symbol VARCHAR(20),
                    alert_type VARCHAR(80),
                    severity VARCHAR(20),
                    title VARCHAR(250),
                    message TEXT,
                    source VARCHAR(120),
                    acknowledged BOOLEAN DEFAULT FALSE,
                    acknowledged_at TIMESTAMP WITHOUT TIME ZONE,
                    resolved BOOLEAN DEFAULT FALSE,
                    resolved_at TIMESTAMP WITHOUT TIME ZONE
                )
            """))

            self.db.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_recommendation_alerts_active
                ON recommendation_alerts (resolved, acknowledged, severity)
            """))

            self.db.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_recommendation_alerts_portfolio_created
                ON recommendation_alerts (portfolio_id, created_at DESC)
            """))

            self.db.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_recommendation_alerts_symbol
                ON recommendation_alerts (symbol)
            """))

            self.db.commit()

        except Exception:
            self._rollback_safe()
            raise

    def get_active_alerts(
        self,
        portfolio_id: Optional[str] = None,
        persist: bool = False,
    ) -> pd.DataFrame:
        alerts: List[RecommendationAlert] = []

        alerts.extend(self._collect_target_alerts(portfolio_id))
        alerts.extend(self._collect_stop_alerts(portfolio_id))
        alerts.extend(self._collect_trade_management_alerts(portfolio_id))
        alerts.extend(self._collect_portfolio_risk_alerts(portfolio_id))
        alerts.extend(self._collect_lifecycle_alerts(portfolio_id))

        deduped = self._dedupe_alerts(alerts)

        if persist and deduped:
            self.persist_alerts(deduped)

        df = pd.DataFrame([a.to_dict() for a in deduped])

        if df.empty:
            return df

        df["severity_rank"] = df["severity"].map(
            lambda x: self.SEVERITY_ORDER.get(str(x).upper(), 99)
        )

        return (
            df.sort_values(["severity_rank", "created_at"], ascending=[True, False])
            .drop(columns=["severity_rank"])
            .reset_index(drop=True)
        )

    def _collect_target_alerts(self, portfolio_id: Optional[str]) -> List[RecommendationAlert]:
        alerts: List[RecommendationAlert] = []

        try:
            raw_alerts = self.target_engine.get_target_alerts(portfolio_id)
        except Exception:
            self._rollback_safe()
            return alerts

        for a in raw_alerts:
            symbol = str(a.get("symbol", "")).upper()

            alerts.append(
                RecommendationAlert(
                    symbol=symbol,
                    portfolio_id=portfolio_id,
                    alert_type=str(a.get("alert_type", "TARGET_ALERT")),
                    severity=str(a.get("severity", "INFO")).upper(),
                    title=f"{symbol} Target Alert",
                    message=str(a.get("message", "")),
                    source="RecommendationTargetTrackingEngine",
                    recommendation_id=a.get("recommendation_id"),
                    created_at=datetime.utcnow(),
                )
            )

        return alerts

    def _collect_stop_alerts(self, portfolio_id: Optional[str]) -> List[RecommendationAlert]:
        alerts: List[RecommendationAlert] = []

        try:
            raw_alerts = self.stop_engine.get_stop_alerts(portfolio_id)
        except Exception:
            self._rollback_safe()
            return alerts

        for a in raw_alerts:
            symbol = str(a.get("symbol", "")).upper()

            alerts.append(
                RecommendationAlert(
                    symbol=symbol,
                    portfolio_id=portfolio_id,
                    alert_type=str(a.get("alert_type", "STOP_ALERT")),
                    severity=str(a.get("severity", "INFO")).upper(),
                    title=f"{symbol} Stop-Loss Alert",
                    message=str(a.get("message", "")),
                    source="RecommendationStopLossMonitor",
                    recommendation_id=a.get("recommendation_id"),
                    created_at=datetime.utcnow(),
                )
            )

        return alerts

    def _collect_trade_management_alerts(self, portfolio_id: Optional[str]) -> List[RecommendationAlert]:
        alerts: List[RecommendationAlert] = []

        if not portfolio_id:
            return alerts

        try:
            df = self.trade_management_engine.get_trade_management_dataframe(portfolio_id)
        except Exception:
            self._rollback_safe()
            return alerts

        if df.empty:
            return alerts

        for _, row in df.iterrows():
            status = str(row.get("status", "")).upper()
            symbol = str(row.get("symbol", "")).upper()

            if status not in {"STOP_ALERT", "TARGET_HIT", "TRAILING_PROFIT", "CAUTION"}:
                continue

            severity = "INFO"
            alert_type = "TRADE_STATUS"

            if status == "STOP_ALERT":
                severity = "CRITICAL"
                alert_type = "TRADE_STOP_ALERT"
            elif status == "TARGET_HIT":
                severity = "HIGH"
                alert_type = "TRADE_TARGET_HIT"
            elif status == "TRAILING_PROFIT":
                severity = "MEDIUM"
                alert_type = "TRAILING_PROFIT"
            elif status == "CAUTION":
                severity = "MEDIUM"
                alert_type = "TRADE_CAUTION"

            alerts.append(
                RecommendationAlert(
                    symbol=symbol,
                    portfolio_id=portfolio_id,
                    alert_type=alert_type,
                    severity=severity,
                    title=f"{symbol} Trade Management Alert",
                    message=str(row.get("message", "")),
                    source="TradeManagementEngine",
                    created_at=datetime.utcnow(),
                )
            )

        return alerts

    def _collect_portfolio_risk_alerts(self, portfolio_id: Optional[str]) -> List[RecommendationAlert]:
        alerts: List[RecommendationAlert] = []

        if not portfolio_id:
            return alerts

        try:
            breaches = self.portfolio_risk_monitor.concentration_breaches(portfolio_id=portfolio_id)
        except Exception:
            self._rollback_safe()
            return alerts

        if breaches.empty:
            return alerts

        for _, row in breaches.iterrows():
            breach_type = str(row.get("breach_type", "RISK_BREACH"))
            symbol_or_sector = str(row.get("symbol_or_sector", "Portfolio"))
            severity = str(row.get("severity", "MEDIUM")).upper()

            alert_type = (
                "POSITION_CONCENTRATION"
                if breach_type == "POSITION_CONCENTRATION"
                else "SECTOR_CONCENTRATION"
            )

            alerts.append(
                RecommendationAlert(
                    symbol=symbol_or_sector[:20],
                    portfolio_id=portfolio_id,
                    alert_type=alert_type,
                    severity=severity,
                    title=f"{symbol_or_sector} Concentration Alert",
                    message=str(row.get("message", "")),
                    source="PortfolioRiskMonitor",
                    created_at=datetime.utcnow(),
                )
            )

        return alerts

    def _collect_lifecycle_alerts(self, portfolio_id: Optional[str]) -> List[RecommendationAlert]:
        alerts: List[RecommendationAlert] = []

        try:
            lifecycle = self.lifecycle_engine.generate_lifecycle_view(portfolio_id)
        except Exception:
            self._rollback_safe()
            return alerts

        if lifecycle.empty:
            return alerts

        for _, row in lifecycle.iterrows():
            status = str(row.get("status", "")).upper()
            symbol = str(row.get("symbol", "")).upper()

            if status not in {
                "EXPIRED",
                "TARGET_APPROACHING",
                "TARGET_HIT",
                "STOP_APPROACHING",
                "STOP_HIT",
            }:
                continue

            severity = "INFO"
            alert_type = status

            if status == "EXPIRED":
                severity = "LOW"
                alert_type = "RECOMMENDATION_EXPIRED"
            elif status == "TARGET_APPROACHING":
                severity = "MEDIUM"
            elif status == "TARGET_HIT":
                severity = "HIGH"
            elif status == "STOP_APPROACHING":
                severity = "HIGH"
            elif status == "STOP_HIT":
                severity = "CRITICAL"

            alerts.append(
                RecommendationAlert(
                    symbol=symbol,
                    portfolio_id=portfolio_id,
                    alert_type=alert_type,
                    severity=severity,
                    title=f"{symbol} Lifecycle Alert",
                    message=f"{symbol} lifecycle status is {status}.",
                    source="RecommendationLifecycleEngine",
                    recommendation_id=row.get("recommendation_id"),
                    created_at=datetime.utcnow(),
                )
            )

        return alerts

    def persist_alerts(self, alerts: List[RecommendationAlert]) -> int:
        self.ensure_schema()

        inserted = 0

        try:
            for alert in alerts:
                if self._alert_exists(alert):
                    continue

                self.db.execute(
                    text("""
                        INSERT INTO recommendation_alerts (
                            created_at,
                            recommendation_id,
                            portfolio_id,
                            symbol,
                            alert_type,
                            severity,
                            title,
                            message,
                            source,
                            acknowledged,
                            resolved
                        )
                        VALUES (
                            :created_at,
                            :recommendation_id,
                            :portfolio_id,
                            :symbol,
                            :alert_type,
                            :severity,
                            :title,
                            :message,
                            :source,
                            FALSE,
                            FALSE
                        )
                    """),
                    {
                        "created_at": alert.created_at or datetime.utcnow(),
                        "recommendation_id": alert.recommendation_id,
                        "portfolio_id": alert.portfolio_id,
                        "symbol": alert.symbol,
                        "alert_type": alert.alert_type,
                        "severity": alert.severity,
                        "title": alert.title,
                        "message": alert.message,
                        "source": alert.source,
                    },
                )

                inserted += 1

            self.db.commit()
            return inserted

        except Exception:
            self._rollback_safe()
            raise

    def _alert_exists(self, alert: RecommendationAlert) -> bool:
        self.ensure_schema()

        row = self.db.execute(
            text("""
                SELECT id
                FROM recommendation_alerts
                WHERE COALESCE(portfolio_id, '') = COALESCE(:portfolio_id, '')
                  AND COALESCE(symbol, '') = COALESCE(:symbol, '')
                  AND COALESCE(alert_type, '') = COALESCE(:alert_type, '')
                  AND resolved = FALSE
                LIMIT 1
            """),
            {
                "portfolio_id": alert.portfolio_id,
                "symbol": alert.symbol,
                "alert_type": alert.alert_type,
            },
        ).fetchone()

        return row is not None

    def load_persisted_alerts(
        self,
        portfolio_id: Optional[str] = None,
        include_resolved: bool = False,
        limit: int = 250,
    ) -> pd.DataFrame:
        self.ensure_schema()

        sql = """
            SELECT *
            FROM recommendation_alerts
            WHERE 1=1
        """

        params: Dict[str, Any] = {"limit": int(limit)}

        if portfolio_id:
            sql += " AND portfolio_id = :portfolio_id "
            params["portfolio_id"] = portfolio_id

        if not include_resolved:
            sql += " AND resolved = FALSE "

        sql += " ORDER BY created_at DESC LIMIT :limit "

        return pd.read_sql(text(sql), self.db.bind, params=params)

    def acknowledge_alert(self, alert_id: int) -> None:
        self.ensure_schema()

        try:
            self.db.execute(
                text("""
                    UPDATE recommendation_alerts
                    SET acknowledged = TRUE,
                        acknowledged_at = :ts
                    WHERE id = :id
                """),
                {"id": int(alert_id), "ts": datetime.utcnow()},
            )
            self.db.commit()

        except Exception:
            self._rollback_safe()
            raise

    def resolve_alert(self, alert_id: int) -> None:
        self.ensure_schema()

        try:
            self.db.execute(
                text("""
                    UPDATE recommendation_alerts
                    SET resolved = TRUE,
                        resolved_at = :ts
                    WHERE id = :id
                """),
                {"id": int(alert_id), "ts": datetime.utcnow()},
            )
            self.db.commit()

        except Exception:
            self._rollback_safe()
            raise

    def get_alert_counts(self, portfolio_id: Optional[str] = None) -> Dict[str, Any]:
        alerts = self.get_active_alerts(portfolio_id=portfolio_id, persist=False)

        if alerts.empty:
            return {
                "total": 0,
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
                "info": 0,
            }

        severity = alerts["severity"].fillna("INFO").astype(str).str.upper()

        return {
            "total": int(len(alerts)),
            "critical": int((severity == "CRITICAL").sum()),
            "high": int((severity == "HIGH").sum()),
            "medium": int((severity == "MEDIUM").sum()),
            "low": int((severity == "LOW").sum()),
            "info": int((severity == "INFO").sum()),
        }

    def generate_alert_summary(self, portfolio_id: Optional[str] = None) -> Dict[str, Any]:
        active = self.get_active_alerts(portfolio_id=portfolio_id, persist=False)
        persisted = self.load_persisted_alerts(
            portfolio_id=portfolio_id,
            include_resolved=False,
            limit=250,
        )

        return {
            "generated_at": datetime.utcnow().isoformat(),
            "active_alerts": int(len(active)),
            "persisted_unresolved": int(len(persisted)),
            "counts": self.get_alert_counts(portfolio_id),
        }

    def _dedupe_alerts(self, alerts: List[RecommendationAlert]) -> List[RecommendationAlert]:
        seen = set()
        out: List[RecommendationAlert] = []

        for alert in alerts:
            key = (
                alert.portfolio_id,
                alert.symbol,
                alert.alert_type,
                alert.source,
            )

            if key in seen:
                continue

            seen.add(key)
            out.append(alert)

        return out

    def self_test(self, portfolio_id: Optional[str] = None) -> Dict[str, Any]:
        try:
            self.ensure_schema()

            active = self.get_active_alerts(
                portfolio_id=portfolio_id,
                persist=False,
            )

            counts = self.get_alert_counts(portfolio_id=portfolio_id)

            summary = self.generate_alert_summary(
                portfolio_id=portfolio_id,
            )

            return {
                "success": True,
                "active_rows": int(len(active)),
                "counts": counts,
                "summary": summary,
            }

        except Exception as exc:
            self._rollback_safe()
            return {
                "success": False,
                "error": str(exc),
            }