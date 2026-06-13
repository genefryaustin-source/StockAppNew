from __future__ import annotations
from typing import Any
import pandas as pd


def monitor_exposure(positions: list[dict[str, Any]], nav: float) -> dict[str, Any]:
    nav = max(float(nav or 1), 1)
    rows = []
    for p in positions or []:
        mv = float(p.get('market_value') or 0)
        rows.append({'symbol': p.get('symbol'), 'sector': p.get('sector', 'Unknown'), 'market_value': mv, 'weight': round(mv / nav, 4)})
    df = pd.DataFrame(rows)
    sector = [] if df.empty else df.groupby('sector', dropna=False).agg(market_value=('market_value', 'sum'), weight=('weight', 'sum')).reset_index().to_dict('records')
    return {'positions': rows, 'sector_exposure': sector, 'gross_exposure': round(sum(abs(r['weight']) for r in rows), 4)}
