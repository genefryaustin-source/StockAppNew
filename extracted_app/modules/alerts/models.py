# models.py for Alerts
from datetime import datetime, UTC
from sqlalchemy import Column, String, DateTime, Float, Text, Boolean, Index
from modules.db.core import Base
from modules.db.models import gen_uuid


class AlertEvent(Base):
    __tablename__ = "alert_events"

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, nullable=False, index=True)
    symbol = Column(String, nullable=False, index=True)

    created_at = Column(DateTime, default=lambda: datetime.now(UTC), index=True)

    # Types: RATING_CHANGE / BREAKOUT / BREAKDOWN / LEVEL_TOUCH
    alert_type = Column(String, nullable=False, index=True)

    # Snapshot details
    last_price = Column(Float, nullable=True)
    support = Column(Float, nullable=True)
    resistance = Column(Float, nullable=True)

    # Rating details
    previous_rating = Column(String, nullable=True)
    new_rating = Column(String, nullable=True)

    # Human-readable
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)

    # Workflow
    acknowledged = Column(Boolean, default=False, index=True)
    acknowledged_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_alert_tenant_sym_time", "tenant_id", "symbol", "created_at"),
        Index("ix_alert_tenant_ack", "tenant_id", "acknowledged"),
    )