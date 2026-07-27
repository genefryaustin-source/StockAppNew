"""
Forex Quant Research DB Utilities - Sprint 25 Phase 3

Postgres-first SQLAlchemy utilities for tenant-aware forex quant research persistence.
"""

from __future__ import annotations

from typing import Any

from modules.forex.forex_quant_research_engine import (
    DEFAULT_RESEARCH_TABLE,
    DEFAULT_SIGNAL_TABLE,
    ensure_forex_quant_research_tables,
)


def initialize_forex_quant_research_schema(db: Any) -> None:
    """Initialize all Sprint 25 Phase 3 Postgres tables and indexes."""
    ensure_forex_quant_research_tables(db)


__all__ = [
    "DEFAULT_RESEARCH_TABLE",
    "DEFAULT_SIGNAL_TABLE",
    "initialize_forex_quant_research_schema",
    "ensure_forex_quant_research_tables",
]
