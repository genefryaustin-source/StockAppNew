from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .legal_workflow_event_sink import build_sql_legal_audit_sink
from .legal_workflow_repository import (
    InMemoryLegalWorkflowRepository,
    LegalWorkflowRepository,
)
from .legal_workflow_sql_repository import (
    SqlAlchemyLegalWorkflowRepository,
)
from .legal_workflow_service import LegalWorkflowService


@dataclass(frozen=True)
class LegalWorkflowRuntime:
    repository: LegalWorkflowRepository
    service: LegalWorkflowService
    persistence_mode: str


_RUNTIME: LegalWorkflowRuntime | None = None


def build_legal_workflow_runtime(
    *,
    session_factory: Callable[[], Session] | None = None,
    database_url: str | None = None,
    force_memory: bool = False,
) -> LegalWorkflowRuntime:
    if force_memory:
        repository = InMemoryLegalWorkflowRepository()
        return LegalWorkflowRuntime(
            repository=repository,
            service=LegalWorkflowService(repository),
            persistence_mode="memory",
        )

    resolved_url = database_url or os.getenv("DATABASE_URL")

    if session_factory is None and resolved_url:
        engine = create_engine(
            resolved_url,
            pool_pre_ping=True,
            future=True,
        )
        session_factory = sessionmaker(
            bind=engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )

    if session_factory is not None:
        repository = SqlAlchemyLegalWorkflowRepository(session_factory)
        audit_sink = build_sql_legal_audit_sink(session_factory)
        return LegalWorkflowRuntime(
            repository=repository,
            service=LegalWorkflowService(
                repository,
                audit_sink=audit_sink,
            ),
            persistence_mode="sqlalchemy",
        )

    repository = InMemoryLegalWorkflowRepository()
    return LegalWorkflowRuntime(
        repository=repository,
        service=LegalWorkflowService(repository),
        persistence_mode="memory",
    )


def get_legal_workflow_runtime(
    *,
    session_factory: Callable[[], Session] | None = None,
    database_url: str | None = None,
    force_memory: bool = False,
) -> LegalWorkflowRuntime:
    global _RUNTIME

    if _RUNTIME is None:
        _RUNTIME = build_legal_workflow_runtime(
            session_factory=session_factory,
            database_url=database_url,
            force_memory=force_memory,
        )

    return _RUNTIME


def reset_legal_workflow_runtime() -> None:
    global _RUNTIME
    _RUNTIME = None
