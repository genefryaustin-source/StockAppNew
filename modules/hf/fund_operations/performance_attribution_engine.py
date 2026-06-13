from __future__ import annotations
from typing import Any
import pandas as pd


def attribute_performance(positions: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    total_pnl = sum(float(p.get('pnl') or 0) for p in positions or [])
    for p in positions or []:
        pnl = float(p.get('pnl') or 0)
        rows.append({
            'symbol': p.get('symbol'),
            'sector': p.get('sector', 'Unknown'),
            'market_value': float(p.get('market_value') or 0),
            'pnl': round(pnl, 2),
            'contribution_pct': round(pnl / total_pnl, 4) if total_pnl else 0,
        })
    sector = pd.DataFrame(rows)
    sector_rows = [] if sector.empty else sector.groupby('sector', dropna=False).agg(pnl=('pnl', 'sum'), market_value=('market_value', 'sum')).reset_index().to_dict('records')
    return {'position_attribution': rows, 'sector_attribution': sector_rows, 'total_pnl': round(total_pnl, 2)}
