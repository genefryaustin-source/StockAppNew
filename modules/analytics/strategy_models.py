from datetime import datetime, UTC
from sqlalchemy import Column, String, DateTime, Float, Text, Index
from modules.db.core import Base
from modules.db.models import gen_uuid


class DiscoveredStrategy(Base):
    """
    Stores AI-discovered strategies from Phase 18
    """

    __tablename__ = "discovered_strategies"

    id = Column(String, primary_key=True, default=gen_uuid)

    tenant_id = Column(String, nullable=False, index=True)

    name = Column(String, nullable=False)
    factors = Column(String, nullable=True)

    holdings = Column(Text, nullable=True)

    return_pct = Column(Float, nullable=True)
    spy_return = Column(Float, nullable=True)
    alpha = Column(Float, nullable=True)
    sharpe = Column(Float, nullable=True)
    max_drawdown = Column(Float, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    __table_args__ = (
        Index("ix_strategy_tenant_name", "tenant_id", "name"),
    )