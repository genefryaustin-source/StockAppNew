from __future__ import annotations
from typing import Any


def build_lp_statement(lp_name: str, capital_account: float, fund_return: float, fees: float = 0.0) -> dict[str, Any]:
    ending = float(capital_account or 0) * (1 + float(fund_return or 0)) - float(fees or 0)
    return {'lp_name': lp_name, 'beginning_capital': round(capital_account, 2), 'fund_return': round(fund_return, 4), 'fees': round(fees, 2), 'ending_capital': round(ending, 2)}
