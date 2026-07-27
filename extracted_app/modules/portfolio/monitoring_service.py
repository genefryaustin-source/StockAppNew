from __future__ import annotations

from datetime import datetime, timedelta, UTC
import pandas as pd


class MonitoringService:
    def __init__(self):
        self.last_heartbeat: datetime | None = None
        self.last_cycle_status: str = "idle"
        self.last_cycle_message: str = ""
        self.audit_log: list[dict] = []

    def heartbeat(self, status: str = "ok", message: str = "") -> None:
        self.last_heartbeat = datetime.now(UTC)
        self.last_cycle_status = status
        self.last_cycle_message = message

    def is_stale(self, max_age_seconds: int = 180) -> bool:
        if self.last_heartbeat is None:
            return True
        return datetime.now(UTC) - self.last_heartbeat > timedelta(seconds=max_age_seconds)

    def log_event(
        self,
        event_type: str,
        status: str,
        message: str,
        strategy_name: str | None = None,
        portfolio_id: int | None = None,
        metadata: dict | None = None,
    ) -> None:
        self.audit_log.insert(0, {
            "Timestamp": datetime.now(UTC),
            "Event Type": event_type,
            "Status": status,
            "Message": message,
            "Strategy": strategy_name,
            "Portfolio ID": portfolio_id,
            "Metadata": metadata or {},
        })
        self.audit_log = self.audit_log[:500]

    def audit_df(self) -> pd.DataFrame:
        if not self.audit_log:
            return pd.DataFrame()
        return pd.DataFrame(self.audit_log)