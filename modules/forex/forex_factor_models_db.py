"""
Forex Factor Models DB Utilities - Sprint 25 Phase 4

Postgres-first SQLAlchemy utilities for tenant-aware forex factor model persistence.
"""

from __future__ import annotations

from typing import Any

from modules.forex.forex_factor_models_engine import (
    DEFAULT_FACTOR_EXPOSURE_TABLE,
    DEFAULT_FACTOR_SIGNAL_TABLE,
    DEFAULT_FACTOR_SNAPSHOT_TABLE,
    ensure_forex_factor_model_tables,
)


def initialize_forex_factor_models_schema(db: Any) -> None:
    """Initialize all Sprint 25 Phase 4 Postgres tables and indexes."""
    ensure_forex_factor_model_tables(db)


__all__ = [
    "DEFAULT_FACTOR_SNAPSHOT_TABLE",
    "DEFAULT_FACTOR_EXPOSURE_TABLE",
    "DEFAULT_FACTOR_SIGNAL_TABLE",
    "initialize_forex_factor_models_schema",
    "ensure_forex_factor_model_tables",
]
