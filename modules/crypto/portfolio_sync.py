"""
modules/crypto/portfolio_sync.py

The Crypto Portfolio Tracker (modules.crypto.crypto_service._render_portfolio_tracker)
originally kept holdings only in st.session_state -- convenient for a quick
add/remove UI, but invisible to everything else in the app: it vanished on
refresh, and the Internal Risk Layer (which reads modules.risk_layer.positions
straight from the PortfolioPosition/PortfolioSnapshot tables) had no way to
see it.

This module syncs those session-state holdings into a real, tenant-scoped
Portfolio the moment they change, so:
  - they persist like any other portfolio,
  - they show up in the Risk Layer's portfolio scope dropdown,
  - Trading & Execution's broker-agnostic risk math (VaR, concentration,
    exposure by asset class) picks them up automatically.

Cost basis caveat: the tracker only ever collected symbol + quantity, never
a purchase price, so there's no real cost basis to sync. avg_cost is set to
the current price the *first* time a symbol is synced (unrealized P&L = 0
at that moment) and left alone on subsequent syncs so it behaves like a
real cost basis from then on, rather than being silently reset to the
current price (and therefore always showing $0 P&L) on every rerun.
"""

from __future__ import annotations

from datetime import datetime, UTC
from typing import Optional
import uuid

from models.trading import Portfolio, PortfolioPosition, PortfolioSnapshot

TRACKER_PORTFOLIO_NAME = "Crypto Tracker"


def load_crypto_holdings_from_portfolio(db, user: dict) -> list[dict]:
    """
    Loads previously-synced holdings back out of the "Crypto Tracker"
    portfolio so the Add Holdings widget can be initialized from them on
    a fresh session/page load, instead of always starting empty. Returns
    the same shape the tracker's session_state list uses:
    [{"coin_id": str, "symbol": str, "qty": float}, ...].
    """
    from modules.crypto.data_service import COIN_SYMBOLS

    tenant_id = user.get("tenant_id") if user else None
    portfolio = (
        db.query(Portfolio)
        .filter(Portfolio.tenant_id == tenant_id, Portfolio.name == TRACKER_PORTFOLIO_NAME)
        .first()
    )
    if not portfolio:
        return []

    rows = db.query(PortfolioPosition).filter(PortfolioPosition.portfolio_id == portfolio.id).all()
    if not rows:
        return []

    sym_to_id = {v.upper(): k for k, v in COIN_SYMBOLS.items()}
    return [
        {"coin_id": sym_to_id.get(r.symbol.upper(), r.symbol.lower()), "symbol": r.symbol, "qty": float(r.qty or 0.0)}
        for r in rows
    ]


def _get_or_create_tracker_portfolio(db, tenant_id: Optional[str]) -> Portfolio:
    portfolio = (
        db.query(Portfolio)
        .filter(Portfolio.tenant_id == tenant_id, Portfolio.name == TRACKER_PORTFOLIO_NAME)
        .first()
    )
    if portfolio:
        return portfolio

    portfolio = Portfolio(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        name=TRACKER_PORTFOLIO_NAME,
        description="Auto-synced from the Crypto Portfolio Tracker's Add Holdings widget.",
        base_currency="USD",
        starting_cash=0.0,
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(portfolio)
    db.commit()
    return portfolio


def sync_crypto_holdings_to_portfolio(db, user: dict, enriched_holdings: list[dict]) -> None:
    """
    enriched_holdings: list of {"symbol": str, "qty": float, "price": float,
    "value": float} as already computed by _render_portfolio_tracker.
    Safe to call on every render -- positions are upserted by symbol, and
    duplicate-symbol entries (added twice via the UI) are summed first.
    """
    tenant_id = user.get("tenant_id") if user else None
    if not enriched_holdings:
        # Nothing held -- clear out any previously-synced positions instead
        # of leaving stale rows behind after a "Clear Portfolio" click.
        portfolio = _get_or_create_tracker_portfolio(db, tenant_id)
        db.query(PortfolioPosition).filter(PortfolioPosition.portfolio_id == portfolio.id).delete()
        db.commit()
        return

    portfolio = _get_or_create_tracker_portfolio(db, tenant_id)

    # Collapse duplicate symbol entries (the tracker just appends on "Add",
    # so adding BTC twice creates two rows in session_state).
    by_symbol: dict[str, dict] = {}
    for h in enriched_holdings:
        sym = h["symbol"].upper().strip()
        if sym in by_symbol:
            by_symbol[sym]["qty"] += h["qty"]
            by_symbol[sym]["value"] += h["value"]
        else:
            by_symbol[sym] = {"qty": h["qty"], "price": h["price"], "value": h["value"]}

    existing = {
        p.symbol: p
        for p in db.query(PortfolioPosition).filter(PortfolioPosition.portfolio_id == portfolio.id).all()
    }

    total_value = 0.0
    for sym, data in by_symbol.items():
        total_value += data["value"]
        row = existing.get(sym)
        if row:
            row.qty = data["qty"]
            row.market_price = data["price"]
            row.market_value = data["value"]
            row.unrealized_pnl = data["value"] - (row.avg_cost * data["qty"])
            row.updated_at = datetime.utcnow()
        else:
            db.add(PortfolioPosition(
                portfolio_id=portfolio.id, symbol=sym, qty=data["qty"],
                avg_cost=data["price"],  # no real cost basis available -- see module docstring
                market_price=data["price"], market_value=data["value"],
                unrealized_pnl=0.0, realized_pnl=0.0, updated_at=datetime.utcnow(),
            ))

    # Remove positions for symbols no longer held (e.g. after Clear Portfolio
    # then re-adding a subset).
    for sym, row in existing.items():
        if sym not in by_symbol:
            db.delete(row)

    db.add(PortfolioSnapshot(
        portfolio_id=portfolio.id, as_of=datetime.now(UTC),
        cash=0.0, market_value=total_value, equity=total_value,
        realized_pnl=0.0, unrealized_pnl=0.0, net_pnl=0.0,
    ))
    db.commit()
