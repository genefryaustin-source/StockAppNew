"""
execution_service.py

Sprint 37.5
Institutional Execution Framework

Unified Execution Service

This service becomes the single public entry point into the
institutional execution framework.

Every asset class (Forex, Stocks, Options, Crypto, Futures)
should execute through this service.

UI
 ↓
ExecutionService
 ↓
ExecutionPipeline
 ↓
Repositories
 ↓
Portfolio Engine
"""

from __future__ import annotations

from typing import Optional

from .execution_context import ExecutionContext
from .execution_pipeline_factory import (
    ExecutionPipeline,
    build_execution_pipeline,
)


class ExecutionService:
    """
    Institutional execution façade.

    This class intentionally contains almost no business logic.
    It coordinates requests into the execution pipeline.
    """

    def __init__(
        self,
        *,
        db,
        portfolio_engine,
        actor=None,
        source=None,
    ):

        self.db = db

        self.portfolio_engine = portfolio_engine

        self.actor = actor

        self.source = source

        self.pipeline = build_execution_pipeline(
            db=db,
            portfolio_engine=portfolio_engine,
            actor=actor,
            source=source,
        )



    # ------------------------------------------------------------------
    # Market Orders
    # ------------------------------------------------------------------

    def submit_market_order(
        self,
        **kwargs,
    ) -> ExecutionContext:

        context = self.pipeline.submit_request(
            order_type="MARKET",
            **kwargs,
        )

        return self.pipeline.submit(
            context,
        )

    # ------------------------------------------------------------------
    # Limit Orders
    # ------------------------------------------------------------------

    def submit_limit_order(
        self,
        **kwargs,
    ) -> ExecutionContext:

        context = self.pipeline.submit_request(
            order_type="LIMIT",
            **kwargs,
        )

        return self.pipeline.submit(
            context,
        )

    # ------------------------------------------------------------------
    # Stop Orders
    # ------------------------------------------------------------------

    def submit_stop_order(
        self,
        **kwargs,
    ) -> ExecutionContext:

        context = self.pipeline.submit_request(
            order_type="STOP",
            **kwargs,
        )

        return self.pipeline.submit(
            context,
        )

    # ------------------------------------------------------------------
    # Generic Submit
    # ------------------------------------------------------------------

    def submit(
        self,
        **kwargs,
    ) -> ExecutionContext:

        context = self.pipeline.submit_request(
            **kwargs,
        )

        return self.pipeline.submit(
            context,
        )

    # ------------------------------------------------------------------
    # Pending Order Fill
    # ------------------------------------------------------------------

    def fill_pending_order(
        self,
        context: ExecutionContext,
    ) -> ExecutionContext:

        return self.pipeline.pending_pipeline.fill(
            context,
        )

    # ------------------------------------------------------------------
    # Modify Pending Order
    # ------------------------------------------------------------------

    def modify_order(
        self,
        context: ExecutionContext,
        **kwargs,
    ) -> ExecutionContext:

        return self.pipeline.pending_pipeline.modify(
            context,
            **kwargs,
        )

    # ------------------------------------------------------------------
    # Cancel Pending Order
    # ------------------------------------------------------------------

    def cancel_order(
        self,
        context: ExecutionContext,
    ) -> ExecutionContext:

        return self.pipeline.pending_pipeline.cancel(
            context,
        )

    # ------------------------------------------------------------------
    # Position Modification
    # ------------------------------------------------------------------

    def modify_position(
        self,
        context: ExecutionContext,
        **kwargs,
    ) -> ExecutionContext:

        return self.pipeline.position_pipeline.modify(
            context,
            **kwargs,
        )

    # ------------------------------------------------------------------
    # Close Position
    # ------------------------------------------------------------------

    def close_position(
        self,
        context: ExecutionContext,
        **kwargs,
    ) -> ExecutionContext:

        return self.pipeline.position_pipeline.close(
            context,
            **kwargs,
        )

    # ------------------------------------------------------------------
    # Reverse Position
    # ------------------------------------------------------------------

    def reverse_position(
        self,
        context: ExecutionContext,
        **kwargs,
    ) -> ExecutionContext:

        return self.pipeline.position_pipeline.reverse(
            context,
            **kwargs,
        )

    # ------------------------------------------------------------------
    # Flatten Account
    # ------------------------------------------------------------------

    def flatten_account(
        self,
        context: ExecutionContext,
    ) -> ExecutionContext:

        return self.pipeline.position_pipeline.flatten(
            context,
        )

    # ------------------------------------------------------------------
    # Synchronize
    # ------------------------------------------------------------------

    def synchronize_account(
        self,
        context: ExecutionContext,
    ) -> ExecutionContext:

        return self.pipeline.snapshot_pipeline.refresh(
            context,
        )

    # ------------------------------------------------------------------
    # Verification
    # ------------------------------------------------------------------

    def verify_execution(
        self,
        context: ExecutionContext,
    ):

        return self.pipeline.verify(
            context,
        )

    # ------------------------------------------------------------------
    # Pipeline Access
    # ------------------------------------------------------------------

    def get_pipeline(
        self,
    ) -> ExecutionPipeline:

        return self.pipeline

    def ensure_order_tables(self) -> None:
        self.pipeline.order_repository.ensure_tables()

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health(
        self,
    ) -> dict:

        return {

            "service": self.__class__.__name__,

            "pipeline": self.pipeline.__class__.__name__,

            "repository": getattr(
                self.pipeline.repository,
                "__class__",
                type(None),
            ).__name__,

            "order_repository": getattr(
                getattr(
                    self.pipeline,
                    "order_repository",
                    None,
                ),
                "__class__",
                type(None),
            ).__name__,

            "validator": getattr(
                self.pipeline.validator,
                "__class__",
                type(None),
            ).__name__,

            "snapshot_pipeline": getattr(
                self.pipeline.snapshot_pipeline,
                "__class__",
                type(None),
            ).__name__,

            "fill_pipeline": getattr(
                self.pipeline.fill_pipeline,
                "__class__",
                type(None),
            ).__name__,

            "pending_pipeline": getattr(
                self.pipeline.pending_pipeline,
                "__class__",
                type(None),
            ).__name__,

            "position_pipeline": getattr(
                self.pipeline.position_pipeline,
                "__class__",
                type(None),
            ).__name__,

            "actor": str(self.actor),

            "source": str(self.source),
        }


# ==============================================================================
# Factory
# ==============================================================================

_SERVICE_CACHE: dict[
    tuple[int, int],
    ExecutionService,
] = {}


def get_execution_service(
    *,
    db,
    portfolio_engine,
    actor=None,
    source=None,
    cache: bool = True,
) -> ExecutionService:

    cache_key = (
        id(db),
        id(portfolio_engine),
    )

    if not cache:

        return ExecutionService(
            db=db,
            portfolio_engine=portfolio_engine,
            actor=actor,
            source=source,
        )

    service = _SERVICE_CACHE.get(cache_key)

    if service is None:

        service = ExecutionService(
            db=db,
            portfolio_engine=portfolio_engine,
            actor=actor,
            source=source,
        )

        _SERVICE_CACHE[cache_key] = service

    return service

