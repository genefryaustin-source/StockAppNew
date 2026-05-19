# models.py in Data
from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime, Text, ForeignKey
)
from sqlalchemy.orm import relationship
from datetime import datetime
from modules.db.core import Base


class PriceHistory(Base):
    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True)
    symbol = Column(String, index=True)
    date = Column(Date, index=True)

    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)

    created_at = Column(DateTime, default=datetime.utcnow)


class FundamentalSnapshot(Base):
    __tablename__ = "fundamentals"

    id = Column(Integer, primary_key=True)
    symbol = Column(String, index=True)
    fiscal_year = Column(String)

    revenue = Column(Float)
    gross_profit = Column(Float)
    operating_income = Column(Float)
    net_income = Column(Float)
    free_cash_flow = Column(Float)
    total_assets = Column(Float)
    total_liabilities = Column(Float)
    total_equity = Column(Float)

    created_at = Column(DateTime, default=datetime.utcnow)


class EarningsEvent(Base):
    __tablename__ = "earnings_events"

    id = Column(Integer, primary_key=True)
    symbol = Column(String, index=True)
    event_date = Column(Date)
    eps_actual = Column(Float)
    eps_est = Column(Float)
    rev_actual = Column(Float)
    rev_est = Column(Float)
    source = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


class TechnicalIndicator(Base):
    __tablename__ = "technical_indicators"

    id = Column(Integer, primary_key=True)
    symbol = Column(String, index=True)
    date = Column(Date)

    rsi = Column(Float)
    macd = Column(Float)
    sma_50 = Column(Float)
    sma_200 = Column(Float)

    created_at = Column(DateTime, default=datetime.utcnow)