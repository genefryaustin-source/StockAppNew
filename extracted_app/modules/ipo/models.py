# ============================================================
# modules/ipo/models.py
# IPO Intelligence Center Models
# ============================================================

from __future__ import annotations

from datetime import datetime, UTC
from sqlalchemy import (
    Column,
    String,
    DateTime,
    Float,
    Text,
    Boolean,
    Index,
    UniqueConstraint,
)

from modules.db.core import Base
from modules.db.models import gen_uuid


class IPOEvent(Base):
    __tablename__ = "ipo_events"

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, nullable=False, index=True)

    symbol = Column(String, nullable=True, index=True)
    company_name = Column(String, nullable=False, index=True)
    exchange = Column(String, nullable=True)

    ipo_date = Column(DateTime, nullable=True, index=True)
    status = Column(String, nullable=True, index=True)  # upcoming, priced, withdrawn, unknown

    price = Column(Float, nullable=True)
    price_low = Column(Float, nullable=True)
    price_high = Column(Float, nullable=True)
    shares = Column(Float, nullable=True)
    deal_size = Column(Float, nullable=True)
    market_cap = Column(Float, nullable=True)

    sector = Column(String, nullable=True, index=True)
    industry = Column(String, nullable=True)
    country = Column(String, nullable=True)

    underwriters = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    source = Column(String, nullable=True, index=True)
    raw_payload = Column(Text, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    __table_args__ = (
        UniqueConstraint("tenant_id", "company_name", "ipo_date", name="uq_ipo_event_tenant_company_date"),
        Index("ix_ipo_tenant_symbol_date", "tenant_id", "symbol", "ipo_date"),
    )


class IPOWatchlistItem(Base):
    __tablename__ = "ipo_watchlist_items"

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=True, index=True)

    ipo_event_id = Column(String, nullable=True, index=True)
    symbol = Column(String, nullable=True, index=True)
    company_name = Column(String, nullable=False, index=True)

    alert_enabled = Column(Boolean, default=True)
    notes = Column(Text, nullable=True)
    status = Column(String, nullable=True, default="watching")

    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", "company_name", name="uq_ipo_watch_tenant_user_company"),
        Index("ix_ipo_watch_tenant_user", "tenant_id", "user_id"),
    )


class IPOResearchNote(Base):
    __tablename__ = "ipo_research_notes"

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=True, index=True)

    ipo_event_id = Column(String, nullable=True, index=True)
    symbol = Column(String, nullable=True, index=True)
    company_name = Column(String, nullable=False, index=True)

    bull_case = Column(Text, nullable=True)
    bear_case = Column(Text, nullable=True)
    red_flags = Column(Text, nullable=True)
    valuation_notes = Column(Text, nullable=True)
    ai_summary = Column(Text, nullable=True)

    source = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    __table_args__ = (
        Index("ix_ipo_research_tenant_company", "tenant_id", "company_name"),
    )
