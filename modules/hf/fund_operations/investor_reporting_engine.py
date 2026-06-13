from __future__ import annotations
from typing import Any


def build_investor_report(fund_name: str, nav: dict[str, Any], performance: dict[str, Any], risk: dict[str, Any]) -> str:
    return f"""# Investor Report — {fund_name}

## NAV
- Net Assets: ${nav.get('net_assets', 0):,.2f}
- NAV / Share: {nav.get('nav_per_share', 0)}

## Performance
- MTD: {performance.get('mtd_return', 0):.2%}
- QTD: {performance.get('qtd_return', 0):.2%}
- YTD: {performance.get('ytd_return', 0):.2%}
- Sharpe: {performance.get('sharpe', 0)}
- Max Drawdown: {performance.get('max_drawdown', 0):.2%}

## Risk
- Gross Exposure: {risk.get('gross_exposure', 0):.1%}
- Largest Position: {risk.get('largest_position_weight', 0):.1%}
- Concentration Risk: {risk.get('concentration_risk')}
"""
