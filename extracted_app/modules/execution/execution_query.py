
"""
execution_query.py

Execution read/query service.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .execution_models import ExecutionEvent
from .execution_repository import ExecutionRepository


class ExecutionQuery:
    def __init__(self, repository: ExecutionRepository):
        self.repository = repository

    def get_event(self, event_id: str) -> Optional[ExecutionEvent]:
        return self.repository.get_event(event_id)

    def recent(self, limit: int = 100) -> List[ExecutionEvent]:
        return self.repository.get_recent(limit)

    def portfolio(self, portfolio_id: str) -> List[ExecutionEvent]:
        return self.repository.get_by_portfolio(portfolio_id)

    def position(self, position_id: str) -> List[ExecutionEvent]:
        return self.repository.get_by_position(position_id)

    def order(self, order_id: str) -> List[ExecutionEvent]:
        return self.repository.get_by_order(order_id)

    def execution(self, execution_id: str) -> List[ExecutionEvent]:
        return self.repository.get_by_execution(execution_id)

    def symbol(self, symbol: str) -> List[ExecutionEvent]:
        return self.repository.get_by_symbol(symbol)

    def timeline(self, correlation_id: str) -> List[ExecutionEvent]:
        events = self.recent(limit=100000)
        return sorted(
            [e for e in events if e.correlation_id == correlation_id],
            key=lambda e: e.occurred_at,
        )

    def position_timeline(self, position_id: str) -> List[ExecutionEvent]:
        return sorted(
            self.position(position_id),
            key=lambda e: e.occurred_at,
        )

    def order_lifecycle(self, order_id: str) -> List[ExecutionEvent]:
        return sorted(
            self.order(order_id),
            key=lambda e: e.occurred_at,
        )

    def symbol_activity(self, symbol: str, limit: int = 500) -> List[ExecutionEvent]:
        return self.symbol(symbol)[:limit]

    def portfolio_summary(self, portfolio_id: str) -> Dict[str, int]:
        events = self.portfolio(portfolio_id)
        counts: Dict[str, int] = {}
        for event in events:
            key = event.event_type.value
            counts[key] = counts.get(key, 0) + 1
        return counts


