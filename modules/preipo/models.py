# ============================================================
# modules/preipo/models.py
# Pre-IPO Intelligence Center Models
# ============================================================

from __future__ import annotations

from datetime import datetime, UTC

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Index,
    String,
    Text,
    UniqueConstraint,
)

from models.base import Base
from modules.db.models import gen_uuid


class PreIPOCompany(Base):
    __tablename__ = "preipo_companies"

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, nullable=False, index=True)

    company_name = Column(String, nullable=False, index=True)
    normalized_name = Column(String, nullable=False, index=True)
    ticker_hint = Column(String, nullable=True, index=True)

    sector = Column(String, nullable=True, index=True)
    industry = Column(String, nullable=True)
    country = Column(String, nullable=True)
    website = Column(String, nullable=True)

    last_known_valuation = Column(Float, nullable=True)
    last_funding_amount = Column(Float, nullable=True)
    last_funding_date = Column(DateTime, nullable=True, index=True)
    last_funding_round = Column(String, nullable=True)
    lead_investors = Column(Text, nullable=True)

    sec_filing_status = Column(String, nullable=True, index=True)
    latest_sec_filing_date = Column(DateTime, nullable=True, index=True)
    latest_sec_filing_type = Column(String, nullable=True)
    latest_sec_filing_url = Column(Text, nullable=True)

    ipo_probability_score = Column(Float, nullable=True, index=True)
    ipo_readiness_score = Column(Float, nullable=True, index=True)
    expected_ipo_window = Column(String, nullable=True)
    confidence = Column(String, nullable=True)

    source = Column(String, nullable=True, index=True)
    raw_payload = Column(Text, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    __table_args__ = (
        UniqueConstraint("tenant_id", "normalized_name", name="uq_preipo_company_tenant_name"),
        Index("ix_preipo_company_tenant_score", "tenant_id", "ipo_probability_score"),
    )


class PreIPOFundingRound(Base):
    __tablename__ = "preipo_funding_rounds"

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, nullable=False, index=True)
    company_id = Column(String, nullable=True, index=True)

    company_name = Column(String, nullable=False, index=True)
    normalized_name = Column(String, nullable=False, index=True)

    round_name = Column(String, nullable=True, index=True)
    round_date = Column(DateTime, nullable=True, index=True)
    amount = Column(Float, nullable=True)
    valuation = Column(Float, nullable=True)
    lead_investors = Column(Text, nullable=True)
    participating_investors = Column(Text, nullable=True)

    source = Column(String, nullable=True, index=True)
    source_url = Column(Text, nullable=True)
    raw_payload = Column(Text, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    __table_args__ = (
        Index("ix_preipo_round_tenant_company_date", "tenant_id", "normalized_name", "round_date"),
    )


class PreIPOFiling(Base):
    __tablename__ = "preipo_filings"

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, nullable=False, index=True)
    company_id = Column(String, nullable=True, index=True)

    company_name = Column(String, nullable=False, index=True)
    normalized_name = Column(String, nullable=False, index=True)
    filing_type = Column(String, nullable=True, index=True)
    filing_date = Column(DateTime, nullable=True, index=True)
    accession_number = Column(String, nullable=True, index=True)
    filing_url = Column(Text, nullable=True)
    cik = Column(String, nullable=True, index=True)
    is_spac = Column(Boolean, default=False, index=True)

    ai_summary = Column(Text, nullable=True)
    risk_factors_summary = Column(Text, nullable=True)
    use_of_proceeds = Column(Text, nullable=True)

    source = Column(String, nullable=True, index=True)
    raw_payload = Column(Text, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    __table_args__ = (
        UniqueConstraint("tenant_id", "accession_number", name="uq_preipo_filing_tenant_accession"),
        Index("ix_preipo_filing_tenant_company_date", "tenant_id", "normalized_name", "filing_date"),
        Index("ix_preipo_filing_tenant_form_date", "tenant_id", "filing_type", "filing_date"),
    )


class PreIPOWatchlistItem(Base):
    __tablename__ = "preipo_watchlist_items"

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=True, index=True)
    company_id = Column(String, nullable=True, index=True)

    company_name = Column(String, nullable=False, index=True)
    normalized_name = Column(String, nullable=False, index=True)
    alert_enabled = Column(Boolean, default=True)
    notes = Column(Text, nullable=True)
    status = Column(String, nullable=True, default="watching")

    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", "normalized_name", name="uq_preipo_watch_tenant_user_company"),
        Index("ix_preipo_watch_tenant_user", "tenant_id", "user_id"),
    )
