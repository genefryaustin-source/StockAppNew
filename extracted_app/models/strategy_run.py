from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey
from models.base import Base


class StrategyRun(Base):
    __tablename__ = "strategy_runs"

    id = Column(Integer, primary_key=True)

    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), nullable=False)
    strategy_name = Column(String(120), nullable=False)

    trigger_type = Column(String(50))  # manual / drift / scheduled
    status = Column(String(50))  # planned / executed / failed

    target_snapshot = Column(Text)  # JSON snapshot of weights
    drift_threshold = Column(Float)

    notes = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)