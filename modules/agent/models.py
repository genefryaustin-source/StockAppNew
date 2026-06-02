"""
modules/agent/models.py

Database models for the Agentic Portfolio Manager.

Tables:
  agent_portfolios   — isolated agent budget + config
  agent_activity_log — every decision with reasoning (the activity feed)
  agent_decisions    — structured trade decisions before execution
"""

from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Float, DateTime, Boolean,
    Text, Integer, Index,
)
from modules.db.core import Base
from modules.db.models import gen_uuid


class AgentPortfolio(Base):
    """
    An isolated agent-managed budget.
    Separate from the user's main portfolio — agent operates within this bubble.
    """
    __tablename__ = "agent_portfolios"

    id            = Column(String, primary_key=True, default=gen_uuid)
    tenant_id     = Column(String, nullable=False, index=True)
    user_id       = Column(String, nullable=True)

    name          = Column(String, nullable=False, default="AI Agent Portfolio")
    strategy_instruction = Column(Text, nullable=False)   # NL strategy e.g. "growth tech stocks"
    budget        = Column(Float,  nullable=False, default=10000.0)   # agent's total budget
    max_positions = Column(Integer, default=10)
    rebalance_schedule = Column(String, default="manual")  # manual / daily / weekly
    risk_level    = Column(String, default="moderate")     # conservative / moderate / aggressive

    # State
    active        = Column(Boolean, default=True)
    killed        = Column(Boolean, default=False)
    kill_reason   = Column(Text, nullable=True)

    # Linked paper portfolio (uses existing OrderService)
    portfolio_id  = Column(String, nullable=True)

    # Metrics
    last_run      = Column(DateTime, nullable=True)
    run_count     = Column(Integer, default=0)
    total_trades  = Column(Integer, default=0)

    created_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_agent_portfolio_tenant", "tenant_id"),
    )


class AgentActivityLog(Base):
    """
    Every agent decision, action, and observation — the real-time activity feed.
    """
    __tablename__ = "agent_activity_log"

    id            = Column(String, primary_key=True, default=gen_uuid)
    agent_id      = Column(String, nullable=False, index=True)
    tenant_id     = Column(String, nullable=False, index=True)

    # What happened
    event_type    = Column(String, nullable=False)
    # Types: CYCLE_START, ANALYSIS, DECISION, TRADE_EXECUTED, TRADE_SKIPPED,
    #        REBALANCE, KILL_SWITCH, ERROR, INFO

    symbol        = Column(String, nullable=True)
    action        = Column(String, nullable=True)    # BUY / SELL / HOLD / SKIP
    qty           = Column(Float, nullable=True)
    price         = Column(Float, nullable=True)
    notional      = Column(Float, nullable=True)

    # The AI's reasoning — shown in the activity feed
    reasoning     = Column(Text, nullable=False, default="")

    # Outcome
    success       = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)

    created_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    __table_args__ = (
        Index("ix_agent_log_agent_time", "agent_id", "created_at"),
    )


class AgentDecision(Base):
    """
    Structured trade decision — what the agent decided to do and why.
    Stored before execution for audit trail.
    """
    __tablename__ = "agent_decisions"

    id            = Column(String, primary_key=True, default=gen_uuid)
    agent_id      = Column(String, nullable=False, index=True)
    cycle_id      = Column(String, nullable=False)   # groups decisions per run

    symbol        = Column(String, nullable=False)
    action        = Column(String, nullable=False)   # BUY / SELL / HOLD
    target_weight = Column(Float, nullable=True)
    target_qty    = Column(Float, nullable=True)
    current_qty   = Column(Float, default=0.0)
    price         = Column(Float, nullable=True)
    notional      = Column(Float, nullable=True)

    confidence    = Column(Float, nullable=True)
    reasoning     = Column(Text, nullable=False, default="")

    executed      = Column(Boolean, default=False)
    execution_error = Column(Text, nullable=True)

    created_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc))