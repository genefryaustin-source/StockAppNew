from datetime import datetime, timedelta, UTC
from sqlalchemy import Column, String, DateTime, Float, Integer, UniqueConstraint, Index
from sqlalchemy.orm import Session
from modules.db.models import Base, gen_uuid

class OHLCVBar(Base):
    __tablename__ = "ohlcv_bars"
    id = Column(String, primary_key=True, default=gen_uuid)
    symbol = Column(String, nullable=False)
    interval = Column(String, nullable=False)  # "1d", "1h", etc.
    ts = Column(DateTime, nullable=False)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)

    __table_args__ = (
        UniqueConstraint("symbol", "interval", "ts", name="uq_symbol_interval_ts"),
        Index("ix_symbol_interval_ts", "symbol", "interval", "ts"),
    )

def upsert_bars(db: Session, symbol: str, interval: str, df):
    # df must have columns: Date/Open/High/Low/Close/Volume
    for _, r in df.iterrows():
        ts = r["Date"].to_pydatetime() if hasattr(r["Date"], "to_pydatetime") else r["Date"]
        bar = db.query(OHLCVBar).filter_by(symbol=symbol, interval=interval, ts=ts).first()
        if not bar:
            bar = OHLCVBar(symbol=symbol, interval=interval, ts=ts)
            db.add(bar)
        bar.open = float(r.get("Open", 0) or 0)
        bar.high = float(r.get("High", 0) or 0)
        bar.low = float(r.get("Low", 0) or 0)
        bar.close = float(r.get("Close", 0) or 0)
        bar.volume = float(r.get("Volume", 0) or 0)
    db.commit()

def read_bars(db: Session, symbol: str, interval: str, lookback_days: int = 400):
    import pandas as pd
    cutoff = datetime.now(UTC) - timedelta(days=lookback_days)
    rows = (
        db.query(OHLCVBar)
        .filter(OHLCVBar.symbol == symbol, OHLCVBar.interval == interval, OHLCVBar.ts >= cutoff)
        .order_by(OHLCVBar.ts.asc())
        .all()
    )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([{
        "Date": r.ts,
        "Open": r.open,
        "High": r.high,
        "Low": r.low,
        "Close": r.close,
        "Volume": r.volume
    } for r in rows])