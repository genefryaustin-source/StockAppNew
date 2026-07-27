from __future__ import annotations

from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, Index

from modules.db.core import Base


class FactorStore(Base):
    """
    Latest factor values per symbol per tenant.
    This is the fast-access table used by rankings,
    strategy discovery, and portfolio construction.
    """

    __tablename__ = "factor_store"

    tenant_id = Column(String, primary_key=True)
    symbol = Column(String, primary_key=True)

    updated_at = Column(DateTime, default=datetime.utcnow, index=True)

    # normalized sector / labels
    sector = Column(String, nullable=True, index=True)
    rating = Column(String, nullable=True)

    # core factor model
    composite = Column(Float, nullable=True, index=True)
    confidence = Column(Float, nullable=True, index=True)

    quality = Column(Float, nullable=True)
    growth = Column(Float, nullable=True)
    value = Column(Float, nullable=True)
    momentum = Column(Float, nullable=True)
    risk = Column(Float, nullable=True)

    # technicals
    rsi = Column(Float, nullable=True)
    sma50 = Column(Float, nullable=True)
    sma200 = Column(Float, nullable=True)
    support = Column(Float, nullable=True)
    resistance = Column(Float, nullable=True)
    volatility = Column(Float, nullable=True)
    drawdown = Column(Float, nullable=True)
    trend = Column(String, nullable=True)

    # fundamentals
    revenue_cagr = Column(Float, nullabe=True)
    revenue_cagr = Column(Float, nullable=True)
    gross_margin = Column(Float, nullable=True)
    op_margin = Column(Float, nullable=True)
    fcf_margin = Column(Float, nullable=True)

    pe = Column(Float, nullable=True)
    ps = Column(Float, nullable=True)
    ev_ebitda = Column(Float, nullable=True)

    __table_args__ = (
        Index("ix_factor_store_tenant_composite", "tenant_id", "composite"),
        Index("ix_factor_store_tenant_sector", "tenant_id", "sector"),
    )