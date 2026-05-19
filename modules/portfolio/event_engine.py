from __future__ import annotations

from collections import deque
from datetime import datetime
import pandas as pd


class EventDrivenExecutionEngine:
    def __init__(self):
        self.queue = deque(maxlen=500)

    def push_event(
        self,
        event_type: str,
        priority: str = "normal",
        payload: dict | None = None,
        source: str = "system",
    ) -> dict:
        event = {
            "timestamp": datetime.utcnow(),
            "event_type": event_type,
            "priority": priority,
            "payload": payload or {},
            "source": source,
            "status": "queued",
        }
        self.queue.appendleft(event)
        return event

    def list_events(self) -> list[dict]:
        return list(self.queue)

    def clear(self) -> None:
        self.queue.clear()

    def pop_next(self) -> dict | None:
        if not self.queue:
            return None

        priority_order = {"critical": 0, "high": 1, "normal": 2, "low": 3}
        items = list(self.queue)
        items.sort(key=lambda e: (priority_order.get(e["priority"], 9), e["timestamp"]))

        next_event = items[0]

        # remove matching object from deque
        for idx, item in enumerate(self.queue):
            if item is next_event:
                del self.queue[idx]
                break

        next_event["status"] = "processing"
        return next_event

    def build_rebalance_event(
        self,
        portfolio_id: int,
        target_df: pd.DataFrame,
        reason: str,
        priority: str = "high",
    ) -> dict:
        payload = {
            "portfolio_id": portfolio_id,
            "reason": reason,
            "target_df": target_df.to_dict(orient="records") if target_df is not None and not target_df.empty else [],
        }
        return self.push_event(
            event_type="rebalance_required",
            priority=priority,
            payload=payload,
            source="portfolio_engine",
        )

    def build_alert_event(
        self,
        portfolio_id: int,
        title: str,
        message: str,
        priority: str = "normal",
    ) -> dict:
        return self.push_event(
            event_type="alert",
            priority=priority,
            payload={
                "portfolio_id": portfolio_id,
                "title": title,
                "message": message,
            },
            source="alerting",
        )