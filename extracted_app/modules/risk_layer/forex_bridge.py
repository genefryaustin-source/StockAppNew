"""
modules/risk_layer/forex_bridge.py

The Forex module keeps its own open positions in a dedicated
`forex_positions` table (modules.forex.forex_portfolio_engine), separate
from the generic PortfolioPosition table modules.risk_layer.positions
reads for equities/options/crypto. That's actually the right call on the
Forex module's part -- leveraged FX positions need fields (leverage,
margin_required, base/quote currency) the generic schema doesn't have --
but it meant forex exposure was invisible to the Risk Layer.

This bridge reads forex_positions via the Forex module's own
ForexPortfolioEngine.list_positions() (no duplicate SQL) and normalizes
it into the same positions_df shape the rest of the Risk Layer uses, with
two extra columns (Leverage, Margin Required) populated only for forex
rows -- so it merges cleanly with equities/crypto/options rows in the
same table.
"""

from __future__ import annotations

from typing import Optional
import pandas as pd

from modules.risk_layer.classification import classify_asset_class


def get_forex_positions_df(db, tenant_id: Optional[str]) -> pd.DataFrame:
    """
    All open forex positions for a tenant, across every forex account,
    normalized to the Risk Layer's standard positions_df columns plus
    Leverage / Margin Required. Returns an empty DataFrame (not an error)
    if the Forex module isn't reachable or the tenant has no open
    positions -- this is read-only and must never break the rest of the
    Risk Layer snapshot.
    """
    if not tenant_id:
        return pd.DataFrame()

    try:
        from modules.forex.forex_portfolio_engine import get_forex_portfolio_engine
        engine = get_forex_portfolio_engine(tenant_id=tenant_id, db=db)
        positions = engine.list_positions(status="OPEN")
    except Exception:
        return pd.DataFrame()

    if not positions:
        return pd.DataFrame()

    rows = []
    for p in positions:
        rows.append({
            "Portfolio ID": p.portfolio_id or f"forex:{p.account_id}",
            "Symbol": p.pair,
            "Quantity": float(p.units or 0.0),
            "Avg Cost": float(p.avg_entry_price or 0.0),
            "Market Price": float(p.current_price or 0.0),
            "Market Value": float(p.market_value or 0.0),
            "Unrealized P&L": float(p.unrealized_pnl or 0.0),
            "Realized P&L": float(p.realized_pnl or 0.0),
            "Side": p.side,
            "Leverage": float(p.leverage or 1.0),
            "Margin Required": float(p.margin_required or 0.0),
        })

    df = pd.DataFrame(rows)
    df["Asset Class"] = df["Symbol"].map(classify_asset_class)
    return df
