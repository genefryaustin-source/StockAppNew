"""
modules/forex/forex_terminal_snapshot_models.py

Sprint 26 - Phase 1
Unified Forex Terminal Snapshot Models

This module contains immutable data models used throughout the
institutional Forex Trading Desk. These models intentionally contain
NO business logic, NO database access, and NO Streamlit dependencies.

Everything displayed in the Trading Desk should ultimately come from a
single ForexTerminalSnapshot instance.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# ==========================================================
# Helpers
# ==========================================================

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _serialize(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, list):
        return [_serialize(v) for v in value]

    if isinstance(value, dict):
        return {k: _serialize(v) for k, v in value.items()}

    return value


class SnapshotModel:
    """Base model for snapshot serialization."""

    def to_dict(self) -> Dict[str, Any]:
        return _serialize(asdict(self))

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]):
        return cls(**payload)


# ==========================================================
# Account
# ==========================================================

@dataclass(slots=True)
class TerminalAccount(SnapshotModel):

    id: str = ""
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    portfolio_id: Optional[str] = None

    currency: str = "USD"

    cash_balance: float = 0.0
    equity: float = 0.0

    buying_power: float = 0.0

    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0

    margin_used: float = 0.0
    margin_available: float = 0.0

    leverage: float = 1.0

    account_status: str = "ACTIVE"

    updated_at: datetime = field(default_factory=utc_now)


# ==========================================================
# Portfolio
# ==========================================================

@dataclass(slots=True)
class TerminalPortfolio(SnapshotModel):

    id: str = ""

    tenant_id: Optional[str] = None
    user_id: Optional[str] = None

    name: str = ""

    total_value: float = 0.0

    open_positions: int = 0

    long_positions: int = 0
    short_positions: int = 0

    gross_exposure: float = 0.0
    net_exposure: float = 0.0

    daily_pnl: float = 0.0

    total_realized_pnl: float = 0.0
    total_unrealized_pnl: float = 0.0

    win_rate: float = 0.0

    summary: Dict[str, Any] = field(default_factory=dict)


# ==========================================================
# Position
# ==========================================================

@dataclass(slots=True)
class TerminalPosition(SnapshotModel):

    id: str = ""

    account_id: str = ""
    portfolio_id: Optional[str] = None

    pair: str = ""

    symbol: str = ""

    side: str = ""

    units: float = 0.0

    avg_entry_price: float = 0.0

    current_price: float = 0.0

    market_value: float = 0.0

    notional: float = 0.0

    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0

    leverage: float = 1.0

    margin_required: float = 0.0

    stop_price: Optional[float] = None
    target_price: Optional[float] = None

    status: str = "OPEN"

    opened_at: datetime = field(default_factory=utc_now)

    updated_at: datetime = field(default_factory=utc_now)

    raw: Dict[str, Any] = field(default_factory=dict)


# ==========================================================
# Orders
# ==========================================================

@dataclass(slots=True)
class TerminalOrder(SnapshotModel):

    broker_order_id: str = ""

    status: str = ""

    broker: str = "paper"

    symbol: str = ""

    pair: str = ""

    side: str = ""

    order_type: str = ""

    quantity: float = 0.0

    avg_fill_price: float = 0.0

    stop_price: Optional[float] = None
    target_price: Optional[float] = None

    created_at: datetime = field(default_factory=utc_now)

    updated_at: datetime = field(default_factory=utc_now)

    raw: Dict[str, Any] = field(default_factory=dict)


# ==========================================================
# Executions
# ==========================================================

@dataclass(slots=True)
class TerminalExecution(SnapshotModel):

    execution_id: str = ""

    broker_order_id: str = ""

    pair: str = ""

    side: str = ""

    quantity: float = 0.0

    price: float = 0.0

    commission: float = 0.0

    slippage: float = 0.0

    executed_at: datetime = field(default_factory=utc_now)

    raw: Dict[str, Any] = field(default_factory=dict)


# ==========================================================
# Performance
# ==========================================================

@dataclass(slots=True)
class TerminalPerformance(SnapshotModel):

    sharpe: float = 0.0

    sortino: float = 0.0

    calmar: float = 0.0

    max_drawdown: float = 0.0

    expectancy: float = 0.0

    profit_factor: float = 0.0

    average_win: float = 0.0

    average_loss: float = 0.0

    monthly_returns: List[Dict[str, Any]] = field(default_factory=list)

    attribution: Dict[str, Any] = field(default_factory=dict)


# ==========================================================
# Risk
# ==========================================================

@dataclass(slots=True)
class TerminalRisk(SnapshotModel):

    risk_score: float = 0.0

    leverage: float = 0.0

    value_at_risk: float = 0.0

    drawdown: float = 0.0

    concentration_score: float = 0.0

    liquidity_score: float = 0.0

    warnings: List[str] = field(default_factory=list)


# ==========================================================
# Exposure
# ==========================================================

@dataclass(slots=True)
class TerminalExposure(SnapshotModel):

    currency_exposure: List[Dict[str, Any]] = field(default_factory=list)

    pair_exposure: List[Dict[str, Any]] = field(default_factory=list)

    gross_exposure: float = 0.0

    net_exposure: float = 0.0


# ==========================================================
# Provider Health
# ==========================================================

@dataclass(slots=True)
class TerminalProviderHealth(SnapshotModel):

    providers: List[Dict[str, Any]] = field(default_factory=list)

    runtime_health: float = 100.0

    failed_providers: List[str] = field(default_factory=list)

    provider_usage: Dict[str, Any] = field(default_factory=dict)

    provider_latency: Dict[str, float] = field(default_factory=dict)


# ==========================================================
# Diagnostics
# ==========================================================

@dataclass(slots=True)
class TerminalDiagnostics(SnapshotModel):

    runtime_id: str = ""

    generated_at: datetime = field(default_factory=utc_now)

    build_ms: float = 0.0

    diagnostics: Dict[str, Any] = field(default_factory=dict)


# ==========================================================
# Master Snapshot
# ==========================================================

@dataclass(slots=True)
class ForexTerminalSnapshot(SnapshotModel):

    runtime_id: str = ""

    generated_at: datetime = field(default_factory=utc_now)

    tenant_id: Optional[str] = None

    user_id: Optional[str] = None

    portfolio_id: Optional[str] = None

    account: TerminalAccount = field(default_factory=TerminalAccount)

    portfolio: TerminalPortfolio = field(default_factory=TerminalPortfolio)

    positions: List[TerminalPosition] = field(default_factory=list)

    open_orders: List[TerminalOrder] = field(default_factory=list)

    filled_orders: List[TerminalOrder] = field(default_factory=list)

    executions: List[TerminalExecution] = field(default_factory=list)

    cash_ledger: List[Dict[str, Any]] = field(default_factory=list)

    performance: TerminalPerformance = field(default_factory=TerminalPerformance)

    risk: TerminalRisk = field(default_factory=TerminalRisk)

    exposure: TerminalExposure = field(default_factory=TerminalExposure)

    provider_health: TerminalProviderHealth = field(default_factory=TerminalProviderHealth)

    executive_ai: Dict[str, Any] = field(default_factory=dict)

    strategy: Dict[str, Any] = field(default_factory=dict)

    diagnostics: TerminalDiagnostics = field(default_factory=TerminalDiagnostics)

    system: Dict[str, Any] = field(default_factory=dict)

    metadata: Dict[str, Any] = field(default_factory=dict)