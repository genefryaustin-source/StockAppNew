from __future__ import annotations

from typing import List, Optional
from datetime import datetime, UTC

from sqlalchemy.orm import Session
from sqlalchemy import func

from modules.universe.models import Universe, UniverseSymbol


# ---------------------------------------------------
# Symbol normalization
# ---------------------------------------------------

def normalize_symbol(symbol: str) -> str | None:

    if not symbol:
        return None

    symbol = symbol.strip().upper()

    # ------------------------------------------------
    # Filter non-equity instruments
    # ------------------------------------------------

    bad_suffixes = (
        ".W", ".WS", ".WT",      # warrants
        ".U", ".R",              # units / rights
        ".P",                    # preferred
        "W", "WS", "WT",         # warrants (no dot format)
        "U", "R",                # units / rights
    )

    for suf in bad_suffixes:
        if symbol.endswith(suf):
            return None

    # remove symbols like BRK/B or weird structured tickers
    if "/" in symbol:
        return None

    # remove extremely long tickers (usually derivatives)
    if len(symbol) > 5:
        return None

    return symbol


# ---------------------------------------------------
# Universe management
# ---------------------------------------------------

def create_universe(
    db: Session,
    tenant_id: str,
    name: str,
    description: Optional[str] = None,
    created_by_user_id: Optional[str] = None,
) -> Universe:

    u = Universe(
        tenant_id=tenant_id,
        name=name,
        description=description,
        created_by_user_id=created_by_user_id,
    )

    db.add(u)
    db.commit()
    db.refresh(u)

    return u


def list_universes(db: Session, tenant_id: str) -> List[Universe]:

    return (
        db.query(Universe)
        .filter(Universe.tenant_id == tenant_id)
        .order_by(Universe.created_at.desc())
        .all()
    )


def delete_universe(db: Session, tenant_id: str, universe_id: str) -> None:

    db.query(UniverseSymbol).filter(
        UniverseSymbol.tenant_id == tenant_id,
        UniverseSymbol.universe_id == universe_id,
    ).delete(synchronize_session=False)

    db.query(Universe).filter(
        Universe.tenant_id == tenant_id,
        Universe.id == universe_id,
    ).delete(synchronize_session=False)

    db.commit()


# ---------------------------------------------------
# Add symbols
# ---------------------------------------------------

def add_symbols(db, tenant_id, universe_id, symbols):

    from modules.utils.symbol_utils import clean_symbol_list

    symbols = clean_symbol_list(symbols)

    inserted = 0

    for sym in symbols:

        sym = normalize_symbol(sym)

        if not sym:
            continue

        exists = (
            db.query(UniverseSymbol)
            .filter(
                UniverseSymbol.tenant_id == tenant_id,
                UniverseSymbol.universe_id == universe_id,
                UniverseSymbol.symbol == sym
            )
            .first()
        )

        if exists:
            continue

        db.add(
            UniverseSymbol(
                tenant_id=tenant_id,
                universe_id=universe_id,
                symbol=sym
            )
        )

        inserted += 1

    db.commit()

    return inserted


# ---------------------------------------------------
# List symbols
# ---------------------------------------------------

def list_symbols(db: Session, tenant_id: str, universe_id: str) -> List[str]:

    rows = (
        db.query(UniverseSymbol.symbol)
        .filter(
            UniverseSymbol.tenant_id == tenant_id,
            UniverseSymbol.universe_id == universe_id,
        )
        .order_by(UniverseSymbol.symbol.asc())
        .all()
    )

    symbols = []

    for r in rows:

        sym = normalize_symbol(r[0])

        if sym:
            symbols.append(sym)

    return symbols


# ---------------------------------------------------
# Remove symbol
# ---------------------------------------------------

def remove_symbol(db: Session, tenant_id: str, universe_id: str, symbol: str) -> None:

    symbol = normalize_symbol(symbol)

    if not symbol:
        return

    db.query(UniverseSymbol).filter(
        UniverseSymbol.tenant_id == tenant_id,
        UniverseSymbol.universe_id == universe_id,
        UniverseSymbol.symbol == symbol,
    ).delete(synchronize_session=False)

    db.commit()

