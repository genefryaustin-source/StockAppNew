# ============================================================
# modules/institutional/models.py
# Institutional Models (NO Watchlist definitions here)
# ============================================================

from datetime import datetime, UTC
from sqlalchemy import Column, String, DateTime, Float, Index, UniqueConstraint, ForeignKey
from modules.db.core import Base
from modules.db.models import gen_uuid
from sqlalchemy.orm import relationship
import uuid



# ============================================================
# FUNDAMENTALS (latest snapshot)
# ============================================================

class FundamentalSnapshot(Base):
    __tablename__ = "fundamental_snapshots"

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, nullable=False, index=True)
    symbol = Column(String, nullable=False, index=True)
    asof = Column(DateTime, default=datetime.utcnow, index=True)

    market_cap = Column(Float, nullable=True)
    revenue_ttm = Column(Float, nullable=True)

    net_income = Column(Float, nullable=True)
    ebitda = Column(Float, nullable=True)

    cash = Column(Float, nullable=True)
    total_debt = Column(Float, nullable=True)
    shares_outstanding = Column(Float, nullable=True)

    sector = Column(String, nullable=True)

    gross_margin = Column(Float, nullable=True)
    op_margin = Column(Float, nullable=True)
    fcf_margin = Column(Float, nullable=True)

    __table_args__ = (
        Index("ix_fund_tenant_sym_asof", "tenant_id", "symbol", "asof"),
    )


# ============================================================
# FINANCIAL HISTORY (Phase 5)
# ============================================================

class FinancialPeriod(Base):
    __tablename__ = "financial_periods"

    id = Column(String, primary_key=True, default=gen_uuid)

    tenant_id = Column(String, nullable=False, index=True)
    symbol = Column(String, nullable=False, index=True)

    period_type = Column(String, nullable=False, index=True)  # annual/quarterly
    period_end = Column(DateTime, nullable=False, index=True)

    fiscal_year = Column(Float, nullable=True)
    fiscal_period = Column(String, nullable=True)

    revenue = Column(Float, nullable=True)
    gross_profit = Column(Float, nullable=True)
    operating_income = Column(Float, nullable=True)
    net_income = Column(Float, nullable=True)

    eps_basic = Column(Float, nullable=True)
    eps_diluted = Column(Float, nullable=True)
    source = Column(String)
    ebitda = Column(Float, nullable=True)

    operating_cash_flow = Column(Float, nullable=True)
    capex = Column(Float, nullable=True)
    free_cash_flow = Column(Float, nullable=True)

    cash = Column(Float, nullable=True)
    total_debt = Column(Float, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("tenant_id", "symbol", "period_type", "period_end", name="uq_fin_period"),
        Index("ix_fin_period_lookup", "tenant_id", "symbol", "period_type", "period_end"),
    )


# ============================================================
# EARNINGS EVENTS
# ============================================================
def gen_uuid():
    return str(uuid.uuid4())

class EarningsEvent(Base):
    __tablename__ = "earnings_events"

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, nullable=False, index=True)
    symbol = Column(String, nullable=False, index=True)
   
    earnings_date = Column(DateTime, nullable=True, index=True)
    event_date = Column(DateTime, nullable=True, index=True)
    time_of_day = Column(String, nullable=True)

    eps_actual = Column(Float, nullable=True)
    eps_estimate = Column(Float, nullable=True)
    
    revenue_actual = Column(Float, nullable=True)
    revenue_estimate = Column(Float, nullable=True)

    source = Column(String, nullable=True)



    eps_est = Column(Float, nullable=True)
    rev_est = Column(Float, nullable=True)
    rev_actual = Column(Float, nullable=True)
    rev_estimate = Column(Float, nullable=True)

    #created_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC)
    )
    __table_args__ = (
        Index("ix_earn_tenant_sym_date", "tenant_id", "symbol", "event_date"),
    )

    # ---------------------------------------
    # Watchlist
    # ---------------------------------------


class Watchlist(Base):
    __tablename__ = "watchlists"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    tenant_id = Column(String, index=True, nullable=False)

    name = Column(String, nullable=False)

    # 🔧 THIS COLUMN WAS MISSING
    created_by_user_id = Column(String, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    items = relationship(
        "WatchlistItem",
        back_populates="watchlist",
        cascade="all, delete-orphan",
    )


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    tenant_id = Column(String, index=True, nullable=False)

    watchlist_id = Column(
        String,
        ForeignKey("watchlists.id"),
        index=True,
        nullable=False,
    )

    symbol = Column(String, index=True, nullable=False)

    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    watchlist = relationship("Watchlist", back_populates="items")
