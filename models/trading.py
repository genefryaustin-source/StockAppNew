from __future__ import annotations

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean
)
from sqlalchemy.orm import relationship
from models.base import Base


# ---------------------------------------------------
# PORTFOLIOS
# ---------------------------------------------------

class Portfolio(Base):
    __tablename__ = "portfolios"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(String(100), nullable=True, index=True)
    name = Column(String(120), nullable=False, index=True)
    description = Column(Text, nullable=True)
    benchmark = Column(String(20), nullable=True, default="SPY")
    base_currency = Column(String(10), nullable=False, default="USD")
    starting_cash = Column(Float, nullable=False, default=100000.0)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)


# ---------------------------------------------------
# ORDERS
# ---------------------------------------------------

class TradeOrder(Base):
    __tablename__ = "trade_orders"

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), index=True, nullable=False)
    user_id = Column(Integer, index=True, nullable=True)

    broker = Column(String(50), nullable=False, default="paper")
    broker_order_id = Column(String(100), nullable=True, index=True)

    symbol = Column(String(20), nullable=False, index=True)
    side = Column(String(10), nullable=False)
    order_type = Column(String(20), nullable=False)
    tif = Column(String(20), nullable=False, default="day")

    qty = Column(Float, nullable=False)
    limit_price = Column(Float, nullable=True)
    stop_price = Column(Float, nullable=True)

    status = Column(String(30), nullable=False, default="pending")
    submitted_at = Column(DateTime, nullable=True)
    filled_at = Column(DateTime, nullable=True)
    canceled_at = Column(DateTime, nullable=True)

    avg_fill_price = Column(Float)
    filled_qty = Column(Float)

    # ✅ ADD THESE
    estimated_commission = Column(Float, nullable=False, default=0.0)
    estimated_slippage = Column(Float, nullable=False, default=0.0)
    actual_commission = Column(Float, nullable=False, default=0.0)
    actual_slippage = Column(Float, nullable=False, default=0.0)

    notes = Column(String)

    fills = relationship("TradeFill", back_populates="order", cascade="all, delete-orphan")


# ---------------------------------------------------
# FILLS
# ---------------------------------------------------

class TradeFill(Base):
    __tablename__ = "trade_fills"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("trade_orders.id"), nullable=False, index=True)

    filled_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    symbol = Column(String(20), nullable=False, index=True)
    side = Column(String(10), nullable=False)
    qty = Column(Float, nullable=False)
    price = Column(Float, nullable=False)

    commission = Column(Float, nullable=False, default=0.0)
    slippage = Column(Float, nullable=False, default=0.0)

    order = relationship("TradeOrder", back_populates="fills")


# ---------------------------------------------------
# POSITIONS
# ---------------------------------------------------

class PortfolioPosition(Base):
    __tablename__ = "portfolio_positions"

    id = Column(Integer, primary_key=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), index=True, nullable=False)
    symbol = Column(String(20), nullable=False, index=True)

    qty = Column(Float, nullable=False, default=0.0)
    avg_cost = Column(Float, nullable=False, default=0.0)

    market_price = Column(Float, nullable=False, default=0.0)
    market_value = Column(Float, nullable=False, default=0.0)

    unrealized_pnl = Column(Float, nullable=False, default=0.0)
    realized_pnl = Column(Float, nullable=False, default=0.0)

    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)


# ---------------------------------------------------
# CASH LEDGER
# ---------------------------------------------------

class PortfolioCashLedger(Base):
    __tablename__ = "portfolio_cash_ledger"

    id = Column(Integer, primary_key=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    entry_type = Column(String(30), nullable=False)   # seed, buy, sell, fee, adjustment
    amount = Column(Float, nullable=False)
    currency = Column(String(10), nullable=False, default="USD")

    trade_order_id = Column(Integer, ForeignKey("trade_orders.id"), nullable=True)
    notes = Column(Text, nullable=True)


# ---------------------------------------------------
# SNAPSHOTS
# ---------------------------------------------------

class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"

    id = Column(Integer, primary_key=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), index=True, nullable=False)
    as_of = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    cash = Column(Float, nullable=False, default=0.0)
    market_value = Column(Float, nullable=False, default=0.0)
    equity = Column(Float, nullable=False, default=0.0)

    realized_pnl = Column(Float, nullable=False, default=0.0)
    unrealized_pnl = Column(Float, nullable=False, default=0.0)
    net_pnl = Column(Float, nullable=False, default=0.0)

class ClosedTrade(Base):
    __tablename__ = "closed_trades"

    id = Column(Integer, primary_key=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), index=True, nullable=False)

    symbol = Column(String(20), nullable=False, index=True)

    opened_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    entry_qty = Column(Float, nullable=False, default=0.0)
    exit_qty = Column(Float, nullable=False, default=0.0)

    entry_price = Column(Float, nullable=False, default=0.0)
    exit_price = Column(Float, nullable=False, default=0.0)

    gross_pnl = Column(Float, nullable=False, default=0.0)
    net_pnl = Column(Float, nullable=False, default=0.0)

    commission = Column(Float, nullable=False, default=0.0)
    slippage = Column(Float, nullable=False, default=0.0)

    holding_period_days = Column(Float, nullable=False, default=0.0)
    side_open = Column(String(10), nullable=True)
    side_close = Column(String(10), nullable=True)

    notes = Column(Text, nullable=True)

