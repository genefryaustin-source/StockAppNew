# models.py for Watchlists
from sqlalchemy import Column, String, ForeignKey, DateTime
from datetime import datetime
from modules.db.models import Base, gen_uuid

class Watchlist(Base):
    __tablename__ = "watchlists"

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"

    id = Column(String, primary_key=True, default=gen_uuid)
    watchlist_id = Column(String, ForeignKey("watchlists.id"))
    symbol = Column(String, nullable=False)