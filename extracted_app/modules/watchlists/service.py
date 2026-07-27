# service.py for Watchlists
from sqlalchemy.orm import Session
from modules.watchlists.models import Watchlist, WatchlistItem

def create_watchlist(db: Session, tenant_id: str, name: str):

    wl = Watchlist(
        tenant_id=tenant_id,
        name=name,
    )

    db.add(wl)
    db.commit()

    return wl


def add_symbol(db: Session, watchlist_id: str, symbol: str):

    item = WatchlistItem(
        watchlist_id=watchlist_id,
        symbol=symbol.upper(),
    )

    db.add(item)
    db.commit()


def get_watchlist_symbols(db: Session, watchlist_id: str):

    rows = db.query(WatchlistItem).filter(
        WatchlistItem.watchlist_id == watchlist_id
    ).all()

    return [r.symbol for r in rows]