"""
modules/risk_layer/positions.py

Builds the normalized, cross-asset positions_df and returns_df the rest of
the Risk Layer runs on -- reading directly from the same PortfolioPosition
/ PortfolioSnapshot tables the Trading & Execution UI already writes to,
across whichever broker (paper, Alpaca, Tradier, IBKR) each portfolio uses.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from models.trading import Portfolio, PortfolioPosition, PortfolioSnapshot
from modules.risk_layer.classification import classify_asset_class


def _portfolio_ids_for_scope(db, tenant_id: Optional[str], portfolio_id: Optional[str]) -> list[str]:
    if portfolio_id:
        return [portfolio_id]
    q = db.query(Portfolio.id).filter(Portfolio.is_active == True)  # noqa: E712
    if tenant_id:
        q = q.filter(Portfolio.tenant_id == tenant_id)
    return [row[0] for row in q.all()]


def get_positions_df(db, tenant_id: Optional[str] = None, portfolio_id: Optional[str] = None) -> pd.DataFrame:
    """
    Cross-asset positions across every portfolio in scope (one portfolio_id,
    or every active portfolio for tenant_id). Columns: Symbol, Asset Class,
    Quantity, Avg Cost, Market Price, Market Value, Unrealized P&L,
    Realized P&L, Weight, Portfolio ID.
    """
    portfolio_ids = _portfolio_ids_for_scope(db, tenant_id, portfolio_id)

    rows = []
    if portfolio_ids:
        rows = (
            db.query(PortfolioPosition)
            .filter(PortfolioPosition.portfolio_id.in_(portfolio_ids))
            .filter(PortfolioPosition.qty != 0)
            .all()
        )

    df = pd.DataFrame([{
        "Portfolio ID": r.portfolio_id,
        "Symbol": r.symbol,
        "Quantity": float(r.qty or 0.0),
        "Avg Cost": float(r.avg_cost or 0.0),
        "Market Price": float(r.market_price or 0.0),
        "Market Value": float(r.market_value or 0.0),
        "Unrealized P&L": float(r.unrealized_pnl or 0.0),
        "Realized P&L": float(r.realized_pnl or 0.0),
    } for r in rows])

    if not df.empty:
        df["Asset Class"] = df["Symbol"].map(classify_asset_class)

    # Forex positions live in the Forex module's own forex_positions table,
    # not PortfolioPosition (they need leverage/margin fields the generic
    # schema doesn't have) -- merge them in for a true cross-asset view.
    # Only done for tenant-wide aggregate scope: the Forex module's
    # position rows aren't reliably tied to a specific equities-style
    # Portfolio, so attributing them to one portfolio_id would be a guess.
    if portfolio_id is None:
        from modules.risk_layer.forex_bridge import get_forex_positions_df
        forex_df = get_forex_positions_df(db, tenant_id)
        if not forex_df.empty:
            df = pd.concat([df, forex_df], ignore_index=True, sort=False)

    if df.empty:
        return pd.DataFrame()

    total_mv = df["Market Value"].abs().sum()
    df["Weight"] = df["Market Value"].abs() / total_mv if total_mv else 0.0

    df = df.sort_values("Market Value", key=lambda s: s.abs(), ascending=False).reset_index(drop=True)

    try:
        from modules.risk_layer.data_quality import validate_positions_df
        df, warnings = validate_positions_df(df)
        df.attrs["data_quality_warnings"] = warnings
    except Exception:
        df.attrs["data_quality_warnings"] = []

    return df


def get_returns_df(db, tenant_id: Optional[str] = None, portfolio_id: Optional[str] = None) -> pd.DataFrame:
    """
    Daily-equity-curve-derived Return/Drawdown series, aggregated across
    every portfolio in scope. Feeds
    modules.portfolio.risk_analytics_service.RiskAnalyticsService directly.

    Two data-quality issues this guards against, since the Trading &
    Execution page writes a new PortfolioSnapshot row on every page render
    (not once a day):

      1. A portfolio can have many snapshot rows on the same calendar day
         (one per page view). Naively summing same-day rows together
         would fabricate a huge equity spike that day, followed by a
         "crash" back to the real value whenever only one snapshot exists
         -- we take the LAST snapshot per portfolio per day instead.
      2. Portfolios don't all get snapshotted on the same days. Summing
         only the days a value happens to exist for every portfolio would
         make the total equity swing every time one portfolio simply
         didn't get a fresh snapshot -- we forward-fill each portfolio's
         last known equity across the combined date range before summing.
    """
    portfolio_ids = _portfolio_ids_for_scope(db, tenant_id, portfolio_id)
    if not portfolio_ids:
        return pd.DataFrame()

    rows = (
        db.query(PortfolioSnapshot)
        .filter(PortfolioSnapshot.portfolio_id.in_(portfolio_ids))
        .order_by(PortfolioSnapshot.as_of.asc())
        .all()
    )
    if not rows:
        return pd.DataFrame()

    raw = pd.DataFrame([{
        "portfolio_id": r.portfolio_id,
        "as_of": r.as_of.date() if hasattr(r.as_of, "date") else r.as_of,
        "equity": float(r.equity or 0.0),
    } for r in rows])

    # One row per (portfolio, day): the LAST snapshot that day, not a sum
    # of every page view that happened to record one.
    daily = raw.sort_values("as_of").groupby(["portfolio_id", "as_of"], as_index=False).last()

    # Align every portfolio onto the same daily index and forward-fill so
    # a portfolio missing a snapshot on a given day contributes its last
    # known equity instead of silently dropping out of that day's total.
    pivot = daily.pivot(index="as_of", columns="portfolio_id", values="equity").sort_index()
    pivot = pivot.ffill()

    curve = pd.DataFrame({"as_of": pivot.index, "equity": pivot.sum(axis=1, skipna=True).values})
    if len(curve) < 2:
        return pd.DataFrame()

    curve["Return"] = curve["equity"].pct_change()
    curve["Drawdown"] = curve["equity"] / curve["equity"].cummax() - 1.0
    curve = curve.dropna(subset=["Return"]).reset_index(drop=True)

    try:
        from modules.risk_layer.data_quality import validate_returns_df
        curve, warnings = validate_returns_df(curve)
        curve.attrs["data_quality_warnings"] = warnings
    except Exception:
        curve.attrs["data_quality_warnings"] = []

    return curve


def portfolio_cash(db, tenant_id: Optional[str] = None, portfolio_id: Optional[str] = None) -> float:
    """Latest total cash across portfolios in scope -- used to compute a
    real cash-buffer percentage for the survival score instead of assuming
    zero cash on hand."""
    portfolio_ids = _portfolio_ids_for_scope(db, tenant_id, portfolio_id)
    if not portfolio_ids:
        return 0.0
    latest_per_portfolio = {}
    rows = (
        db.query(PortfolioSnapshot)
        .filter(PortfolioSnapshot.portfolio_id.in_(portfolio_ids))
        .order_by(PortfolioSnapshot.as_of.asc())
        .all()
    )
    for r in rows:
        latest_per_portfolio[r.portfolio_id] = float(r.cash or 0.0)
    return sum(latest_per_portfolio.values())


def portfolio_equity(db, tenant_id: Optional[str] = None, portfolio_id: Optional[str] = None) -> float:
    portfolio_ids = _portfolio_ids_for_scope(db, tenant_id, portfolio_id)
    if not portfolio_ids:
        return 0.0
    latest_per_portfolio = {}
    rows = (
        db.query(PortfolioSnapshot)
        .filter(PortfolioSnapshot.portfolio_id.in_(portfolio_ids))
        .order_by(PortfolioSnapshot.as_of.asc())
        .all()
    )
    for r in rows:
        latest_per_portfolio[r.portfolio_id] = float(r.equity or 0.0)
    return sum(latest_per_portfolio.values())
