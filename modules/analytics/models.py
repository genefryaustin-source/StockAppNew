from datetime import datetime, UTC
from sqlalchemy import Column, String, DateTime, Float, Text, Index
from modules.db.core import Base
from modules.db.models import gen_uuid


class AnalyticsSnapshot(Base):
    """
    One record per symbol per run (audit trail).

    Phase 6.1 + Phase 7 support:
      - sector
      - factor scores
      - composite + confidence
      - fundamentals
    """

    __tablename__ = "analytics_snapshots"

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, nullable=False, index=True)
    symbol = Column(String, nullable=False, index=True)

    # KEEP UTC-AWARE TIMESTAMPS (your system depends on this)
    asof = Column(DateTime, default=lambda: datetime.now(UTC), index=True)

    # -----------------------------
    # Sector metadata
    # -----------------------------

    sector = Column(String, nullable=True, index=True)

    # -----------------------------
    # Fundamental metrics
    # -----------------------------

    
    gross_margin = Column(Float, nullable=True)
    operating_margin = Column(Float, nullable=True)
    fcf_margin = Column(Float, nullable=True)
    revenue_cagr = Column(Float, nullable=True)

    # -----------------------------
    # Valuation
    # -----------------------------

    pe_ttm = Column(Float, nullable=True)
    ps_ttm = Column(Float, nullable=True)
    ev_ebitda = Column(Float, nullable=True)

    # -----------------------------
    # Technicals
    # -----------------------------

    trend = Column(String, nullable=True)
    rsi_14 = Column(Float, nullable=True)
    sma_50 = Column(Float, nullable=True)
    sma_200 = Column(Float, nullable=True)
    support = Column(Float, nullable=True)
    resistance = Column(Float, nullable=True)

    # -----------------------------
    # Risk
    # -----------------------------

    vol_20d = Column(Float, nullable=True)
    max_drawdown_1y = Column(Float, nullable=True)
    risk_score = Column(Float, nullable=True)

    # -----------------------------
    # Rating
    # -----------------------------

    rating = Column(String, nullable=True)
    rating_rationale = Column(Text, nullable=True)

    # -----------------------------
    # Factor model
    # -----------------------------

    quality_score = Column(Float, nullable=True)
    growth_score = Column(Float, nullable=True)
    value_score = Column(Float, nullable=True)
    momentum_score = Column(Float, nullable=True)
    composite_score = Column(Float, nullable=True)
    confidence_score = Column(Float, nullable=True)
    latest_volume = Column(Float, nullable=True)
    signal = Column(String, nullable=True)
    signal_rationale = Column(String, nullable=True)
    sentiment_score = Column(Float, nullable=True)
    # -----------------------------
    # Convenience properties
    # -----------------------------

    @property
    def quality(self):
        return self.quality_score

    @property
    def growth(self):
        return self.growth_score

    @property
    def value(self):
        return self.value_score

    @property
    def momentum(self):
        return self.momentum_score

    @property
    def risk(self):
        return self.risk_score

    @property
    def composite(self):
        return self.composite_score

    @property
    def confidence(self):
        return self.confidence_score

    # -----------------------------
    # Indexes
    # -----------------------------

    __table_args__ = (
        Index("ix_analytics_tenant_sym_asof", "tenant_id", "symbol", "asof"),
        Index("ix_analytics_tenant_sector_asof", "tenant_id", "sector", "asof"),
        Index("ix_analytics_tenant_sym", "tenant_id", "symbol", unique=True),
    )
    