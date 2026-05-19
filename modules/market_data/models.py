from datetime import datetime, UTC
from sqlalchemy import Column, String, Float, Date, DateTime, Index, Text
from modules.db.core import Base


class MarketDataCache(Base):

    __tablename__ = "market_data_cache"

    symbol = Column(String, primary_key=True)

    latest_price = Column(Float, nullable=True)

    history_json = Column(Text, nullable=True)

    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC)
    )

class PriceHistory(Base):

    __tablename__ = "price_history"

    symbol = Column(String, primary_key=True)
    date = Column(Date, primary_key=True)

    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)

    __table_args__ = (
        Index("ix_price_symbol_date", "symbol", "date"),
    )