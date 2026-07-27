from __future__ import annotations
from typing import Any
from datetime import datetime, timezone


def calculate_nav(positions: list[dict[str, Any]] | None = None, cash: float = 0.0, liabilities: float = 0.0, shares_outstanding: float = 1_000_000) -> dict[str, Any]:
    positions = positions or []
    gross_assets = sum(float(p.get('market_value') or p.get('value') or 0) for p in positions)
    net_assets = gross_assets + float(cash or 0) - float(liabilities or 0)
    nav_per_share = net_assets / max(float(shares_outstanding or 1), 1)
    return {
        'asof': datetime.now(timezone.utc).isoformat(),
        'gross_assets': round(gross_assets, 2),
        'cash': round(float(cash or 0), 2),
        'liabilities': round(float(liabilities or 0), 2),
        'net_assets': round(net_assets, 2),
        'shares_outstanding': round(float(shares_outstanding or 0), 2),
        'nav_per_share': round(nav_per_share, 4),
    }


def sample_positions() -> list[dict[str, Any]]:
    return [
        {'symbol': 'AAPL', 'sector': 'Technology', 'market_value': 125000, 'weight': 0.125, 'pnl': 8200},
        {'symbol': 'MSFT', 'sector': 'Technology', 'market_value': 120000, 'weight': 0.120, 'pnl': 6100},
        {'symbol': 'JPM', 'sector': 'Financials', 'market_value': 90000, 'weight': 0.090, 'pnl': 2400},
        {'symbol': 'UNH', 'sector': 'Healthcare', 'market_value': 85000, 'weight': 0.085, 'pnl': -1200},
        {'symbol': 'XOM', 'sector': 'Energy', 'market_value': 75000, 'weight': 0.075, 'pnl': 3100},
    ]
