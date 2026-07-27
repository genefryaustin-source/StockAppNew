
"""
execution_event_engine.py

High-level execution event recording engine.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from .execution_models import (
    AssetClass,
    ExecutionActor,
    ExecutionContext,
    ExecutionEvent,
    ExecutionEventType,
    ExecutionSource,
)
from .execution_repository import ExecutionRepository


class ExecutionEventEngine:
    def __init__(self, repository: ExecutionRepository):
        self.repository = repository

    def _context(
            self,
            actor: Optional[ExecutionActor] = None,
            source: Optional[ExecutionSource] = None,
            strategy: Optional[str] = None,
    ) -> ExecutionContext:
        return ExecutionContext(
            actor=actor or ExecutionActor.SYSTEM,
            source=source or ExecutionSource.UI,
            strategy=strategy,
        )

    def _build(
        self,
        event_type: ExecutionEventType,
        *,
        asset_class: AssetClass,
        actor: Optional[ExecutionActor] = None,
        source: Optional[ExecutionSource] = None,
        strategy: Optional[str] = None,
        correlation_id: Optional[str] = None,
        **kwargs: Any,
    ) -> ExecutionEvent:
        return ExecutionEvent(
            event_type=event_type,
            asset_class=asset_class,
            correlation_id=correlation_id or str(uuid.uuid4()),
            context=self._context(actor, source, strategy),
            **kwargs,
        )

    def record(self, event: ExecutionEvent) -> ExecutionEvent:
        return self.repository.append(event)

    def record_new_order(self, **kwargs: Any) -> ExecutionEvent:
        event = self._build(ExecutionEventType.NEW_ORDER, **kwargs)
        return self.record(event)

    def record_order_filled(self, **kwargs: Any) -> ExecutionEvent:
        event = self._build(ExecutionEventType.ORDER_FILLED, **kwargs)
        return self.record(event)

    def record_position_opened(self, **kwargs: Any) -> ExecutionEvent:
        event = self._build(ExecutionEventType.POSITION_OPENED, **kwargs)
        return self.record(event)

    def record_position_closed(self, **kwargs: Any) -> ExecutionEvent:
        event = self._build(ExecutionEventType.POSITION_CLOSED, **kwargs)
        return self.record(event)

    def record_position_modified(self, **kwargs: Any) -> ExecutionEvent:
        event = self._build(ExecutionEventType.POSITION_MODIFIED, **kwargs)
        return self.record(event)

    def record_position_reversed(self, **kwargs: Any) -> ExecutionEvent:
        event = self._build(ExecutionEventType.POSITION_REVERSED, **kwargs)
        return self.record(event)

    def record_stop_loss_triggered(self, **kwargs: Any) -> ExecutionEvent:
        event = self._build(ExecutionEventType.STOP_LOSS_TRIGGERED, **kwargs)
        return self.record(event)

    def record_take_profit_triggered(self, **kwargs: Any) -> ExecutionEvent:
        event = self._build(ExecutionEventType.TAKE_PROFIT_TRIGGERED, **kwargs)
        return self.record(event)

    def record_flatten_all(self, **kwargs: Any) -> ExecutionEvent:
        event = self._build(ExecutionEventType.FLATTEN_ALL, **kwargs)
        return self.record(event)

    def record_custom(
        self,
        event_type: ExecutionEventType,
        **kwargs: Any,
    ) -> ExecutionEvent:
        event = self._build(event_type, **kwargs)
        return self.record(event)

    def record_order_validated(self, **kwargs):
        return self.record(
            self._build(
                ExecutionEventType.ORDER_VALIDATED,
                **kwargs,
            )
        )

    def record_order_rejected(self, **kwargs):
        return self.record(
            self._build(
                ExecutionEventType.ORDER_REJECTED,
                **kwargs,
            )
        )

    def record_order_pending(self, **kwargs):
        return self.record(
            self._build(
                ExecutionEventType.ORDER_PENDING,
                **kwargs,
            )
        )

    def record_order_accepted(self, **kwargs):
        return self.record(
            self._build(
                ExecutionEventType.ORDER_ACCEPTED,
                **kwargs,
            )
        )

    def record_order_modified(self, **kwargs):
        return self.record(
            self._build(
                ExecutionEventType.ORDER_MODIFIED,
                **kwargs,
            )
        )

    def record_order_cancelled(self, **kwargs):
        return self.record(
            self._build(
                ExecutionEventType.ORDER_CANCELLED,
                **kwargs,
            )
        )

    def record_order_expired(self, **kwargs):
        return self.record(
            self._build(
                ExecutionEventType.ORDER_EXPIRED,
                **kwargs,
            )
        )

    def record_order_partially_filled(self, **kwargs):
        return self.record(
            self._build(
                ExecutionEventType.ORDER_PARTIALLY_FILLED,
                **kwargs,
            )
        )

    def record_position_scaled_in(self, **kwargs):
        return self.record(
            self._build(
                ExecutionEventType.POSITION_SCALED_IN,
                **kwargs,
            )
        )

    def record_position_scaled_out(self, **kwargs):
        return self.record(
            self._build(
                ExecutionEventType.POSITION_SCALED_OUT,
                **kwargs,
            )
        )

    def record_position_partially_closed(self, **kwargs):
        return self.record(
            self._build(
                ExecutionEventType.POSITION_PARTIALLY_CLOSED,
                **kwargs,
            )
        )

    def record_account_synchronized(self, **kwargs):
        return self.record(
            self._build(
                ExecutionEventType.ACCOUNT_SYNCHRONIZED,
                **kwargs,
            )
        )

    def _record_type(
            self,
            event_type: ExecutionEventType,
            **kwargs,
    ) -> ExecutionEvent:
        return self.record(
            self._build(
                event_type,
                **kwargs,
            )
        )
def record_trailing_stop_triggered(self, **kwargs: Any) -> ExecutionEvent:
    event = self._build(
        ExecutionEventType.TRAILING_STOP_TRIGGERED,
        **kwargs,
    )
    return self.record(event)


def record_margin_call(self, **kwargs: Any) -> ExecutionEvent:
    event = self._build(
        ExecutionEventType.MARGIN_CALL,
        **kwargs,
    )
    return self.record(event)

