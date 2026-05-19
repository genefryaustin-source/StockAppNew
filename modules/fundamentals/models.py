# models.py in Fundamentals
from sqlalchemy import Column, String, Float, DateTime
from datetime import datetime
from modules.db.models import Base, gen_uuid

class FundamentalSnapshot(Base):

    __tablename__ = "fundamentals"

    id = Column(String, primary_key=True, default=gen_uuid)

    symbol = Column(String)

    market_cap = Column(Float)
    pe_ratio = Column(Float)
    revenue = Column(Float)

    created_at = Column(DateTime, default=datetime.utcnow)