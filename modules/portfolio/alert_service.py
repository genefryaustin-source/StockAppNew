from __future__ import annotations

from datetime import datetime
from typing import Any


class AlertService:
    def __init__(self):
        self._alerts: list[dict[str, Any]] = []

    def push(
        self,
        level: str,
        title: str,
        message: str,
        source: str = "system",
        metadata: dict | None = None,
    ) -> dict:
        alert = {
            "timestamp": datetime.utcnow(),
            "level": str(level).lower(),
            "title": title,
            "message": message,
            "source": source,
            "metadata": metadata or {},
        }
        self._alerts.insert(0, alert)
        self._alerts = self._alerts[:200]
        print(f"[ALERT][{alert['level'].upper()}] {title}: {message}")
        return alert

    def list_alerts(self, level: str | None = None) -> list[dict]:
        if level is None:
            return list(self._alerts)
        level = level.lower()
        return [a for a in self._alerts if a["level"] == level]

    def clear(self) -> None:
        self._alerts = []