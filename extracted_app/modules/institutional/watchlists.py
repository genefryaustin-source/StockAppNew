import uuid
from datetime import datetime, UTC

from modules.institutional.models import Watchlist, WatchlistItem


# -----------------------------------------------------
# CREATE WATCHLIST
# -----------------------------------------------------

def create_watchlist(db, tenant_id, name, created_by_user_id=None):

    wl = Watchlist(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        name=name.strip(),
        created_by_user_id=created_by_user_id,
        created_at=datetime.now(UTC)
    )

    db.add(wl)
    db.commit()
    db.refresh(wl)

    return wl


# -----------------------------------------------------
# DELETE WATCHLIST
# -----------------------------------------------------

def delete_watchlist(db, tenant_id, watchlist_id):
    """Deletes a watchlist and all of its items (cascade is configured on
    the Watchlist.items relationship, so this also removes the child
    WatchlistItem rows). Returns True if something was actually deleted.
    """
    wl = (
        db.query(Watchlist)
        .filter(
            Watchlist.id == watchlist_id,
            Watchlist.tenant_id == tenant_id,
        )
        .first()
    )

    if wl is None:
        return False

    db.delete(wl)
    db.commit()

    return True


# -----------------------------------------------------
# LIST WATCHLISTS
# -----------------------------------------------------

def list_watchlists(db, tenant_id):

    return (
        db.query(Watchlist)
        .filter(Watchlist.tenant_id == tenant_id)
        .order_by(Watchlist.created_at.asc())
        .all()
    )


# -----------------------------------------------------
# ADD SYMBOL
# -----------------------------------------------------

def add_symbol(db, tenant_id, watchlist_id, symbol):

    symbol = symbol.upper().strip()

    existing = (
        db.query(WatchlistItem)
        .filter(
            WatchlistItem.watchlist_id == watchlist_id,
            WatchlistItem.symbol == symbol,
        )
        .first()
    )

    if existing:
        return existing

    item = WatchlistItem(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        watchlist_id=watchlist_id,
        symbol=symbol,
        created_at=datetime.now(UTC)
    )

    db.add(item)
    db.commit()
    db.refresh(item)

    return item


# -----------------------------------------------------
# REMOVE SYMBOL
# -----------------------------------------------------

def remove_symbol(db, watchlist_id, symbol):

    symbol = symbol.upper().strip()

    row = (
        db.query(WatchlistItem)
        .filter(
            WatchlistItem.watchlist_id == watchlist_id,
            WatchlistItem.symbol == symbol,
        )
        .first()
    )

    if row:
        db.delete(row)
        db.commit()


# -----------------------------------------------------
# LIST SYMBOLS
# -----------------------------------------------------

def list_symbols(db, watchlist_id):

    rows = (
        db.query(WatchlistItem)
        .filter(
            WatchlistItem.watchlist_id == watchlist_id
        )
        .all()
    )

    return [r.symbol for r in rows]