"""
modules/execution/execution_pipeline_factory.py

Sprint 26
Institutional Execution Framework

Factory responsible for constructing the complete execution
pipeline dependency graph.

This is the ONLY place that wires together:

ExecutionRepository
ExecutionQuery
ExecutionValidator
ExecutionEventEngine
ExecutionEventRecorder
ExecutionSnapshotPipeline
ExecutionFillPipeline
ExecutionPendingOrderPipeline
ExecutionPositionPipeline
ExecutionOrderPipeline

Every trading module requests its execution
pipeline from here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .execution_context import ExecutionContext
from .execution_event_engine import ExecutionEventEngine
from .execution_event_recorder import ExecutionEventRecorder
from .execution_fill_pipeline import ExecutionFillPipeline
from .execution_models import ExecutionActor, ExecutionSource
from .execution_order_pipeline import ExecutionOrderPipeline
from .execution_pending_order_pipeline import ExecutionPendingOrderPipeline
from .execution_position_pipeline import ExecutionPositionPipeline
from .execution_query import ExecutionQuery
from .execution_repository import ExecutionRepository
from .execution_snapshot_pipeline import ExecutionSnapshotPipeline
from .execution_context_validator import ExecutionContextValidator
from .execution_order_repository import ExecutionOrderRepository
# ==========================================================
# Pipeline Container
# ==========================================================


@dataclass(slots=True)
class ExecutionPipeline:
    """
    Complete execution dependency graph.
    """

    repository: ExecutionRepository
    order_repository: ExecutionOrderRepository
    query: ExecutionQuery
    validator: ExecutionContextValidator
    event_engine: ExecutionEventEngine
    recorder: ExecutionEventRecorder
    snapshot_pipeline: ExecutionSnapshotPipeline
    fill_pipeline: ExecutionFillPipeline
    pending_pipeline: ExecutionPendingOrderPipeline
    position_pipeline: ExecutionPositionPipeline
    order_pipeline: ExecutionOrderPipeline


    def submit(
            self,
            context: ExecutionContext,
    ) -> ExecutionContext:
        """
        Execute a complete order lifecycle.

        Delegates to the institutional order pipeline.
        """
        return self.order_pipeline.execute(context)

    def verify(
            self,
            context: ExecutionContext,
    ):
        return self.snapshot_pipeline.verify_execution(context)

    def create_context(
            self,
            **kwargs,
    ) -> ExecutionContext:
        """
        Factory for execution contexts.

        Centralizes all ExecutionContext construction.
        """
        return ExecutionContext(**kwargs)

    def submit_request(
            self,
            **kwargs,
    ) -> ExecutionContext:
        context = self.create_context(**kwargs)

        return self.submit(context)


# ==========================================================
# Factory
# ==========================================================


class ExecutionPipelineFactory:

    """
    Institutional dependency injector.

    Responsible for constructing the entire
    execution pipeline exactly once.
    """

    def __init__(
            self,
            *,
            db,
            portfolio_engine,
            market_executor=None,
            pending_executor=None,
            verify_executor=None,
            cancel_executor=None,
            actor=None,
            source=None,
    ):

        self.db = db

        self.portfolio_engine = portfolio_engine

        self.actor = actor

        self.source = source

        self.market_executor = market_executor
        self.pending_executor = pending_executor
        self.verify_executor = verify_executor
        self.cancel_executor = cancel_executor

    # ------------------------------------------------------

    def build(
            self,
    ) -> ExecutionPipeline:
        repository = ExecutionRepository(self.db)
        order_repository = ExecutionOrderRepository(
            self.db,
        )
        print("=" * 80)
        print("PIPELINE REPOSITORY")
        print(type(repository))
        print(repository.__class__.__module__)
        print(repository.__class__.__name__)
        print("=" * 80)
        query = ExecutionQuery(repository)

        validator = ExecutionContextValidator(
            repository=repository,
            query=query,
        )

        event_engine = ExecutionEventEngine(
            repository=repository,
        )

        recorder = ExecutionEventRecorder(
            engine=event_engine,
            actor=self.actor,
            source=self.source,
        )

        snapshot_pipeline = ExecutionSnapshotPipeline(
            portfolio_engine=self.portfolio_engine,
            execution_repository=repository,
            execution_query=query,
        )

        fill_pipeline = ExecutionFillPipeline(
            portfolio_engine=self.portfolio_engine,
            order_repository=order_repository,
            snapshot_pipeline=snapshot_pipeline,
            recorder=recorder,
        )

        pending_pipeline = ExecutionPendingOrderPipeline(
            order_repository=order_repository,
            snapshot_pipeline=snapshot_pipeline,
            fill_pipeline=fill_pipeline,
            recorder=recorder,
        )

        position_pipeline = ExecutionPositionPipeline(
            portfolio_engine=self.portfolio_engine,
            order_repository=order_repository,
            snapshot_pipeline=snapshot_pipeline,
            recorder=recorder,
        )

        order_pipeline = ExecutionOrderPipeline(
            validator=validator,
            recorder=recorder,
            fill_pipeline=fill_pipeline,
            pending_pipeline=pending_pipeline,
        )

        return ExecutionPipeline(
            repository=repository,
            order_repository=order_repository,
            query=query,
            validator=validator,
            event_engine=event_engine,
            recorder=recorder,
            snapshot_pipeline=snapshot_pipeline,
            fill_pipeline=fill_pipeline,
            pending_pipeline=pending_pipeline,
            position_pipeline=position_pipeline,
            order_pipeline=order_pipeline,
        )


# ==========================================================
# Singleton Builder
# ==========================================================

_PIPELINE_CACHE = {}


def build_execution_pipeline(

    *,

    db,

    portfolio_engine,

    actor=None,

    source=None,

    cache=True,

) -> ExecutionPipeline:

    """
    Builds (or retrieves) the institutional execution pipeline.

    Parameters

        db
            SQLAlchemy session

        portfolio_engine
            Asset-class portfolio engine

        actor
            ExecutionActor

        source
            ExecutionSource

        cache
            Reuse previously built dependency graph

    Returns

        ExecutionPipeline
    """
    actor = actor or ExecutionActor.SYSTEM
    source = source or ExecutionSource.UI
    cache_key = (

        id(db),

        id(portfolio_engine),

    )

    if cache and cache_key in _PIPELINE_CACHE:

        return _PIPELINE_CACHE[cache_key]

    pipeline = ExecutionPipelineFactory(

        db=db,

        portfolio_engine=portfolio_engine,

        actor=actor,

        source=source,

    ).build()

    if cache:

        _PIPELINE_CACHE[cache_key] = pipeline

    return pipeline


# ==========================================================
# Context Helper
# ==========================================================


def create_execution_context(**kwargs) -> ExecutionContext:
    """
    Convenience helper.

    Example

        context = create_execution_context(
            tenant_id=...,
            account_id=...,
            pair="EUR/USD",
            side="BUY",
            units=100000,
        )
    """

    return ExecutionContext(**kwargs)


# ==========================================================
# Cache Management
# ==========================================================


def clear_execution_pipeline_cache():

    """
    Clears cached execution dependency graphs.

    Useful during testing or application reloads.
    """

    _PIPELINE_CACHE.clear()


def execution_pipeline_cache_size() -> int:

    return len(_PIPELINE_CACHE)