def serialize_performance(report):

    if report is None:
        return None

    return {

        "cash_balance": report["cash_balance"],

        "market_value": report["market_value"],

        "total_equity": report["total_equity"],

        "cost_basis": report["cost_basis"],

        "unrealized_pnl": report["unrealized_pnl"],

        "realized_pnl": report["realized_pnl"],

        "total_return": report["total_return"],

        "total_return_pct": report["total_return_pct"],

        "positions": report["positions"],

        "winning_positions": report["winning_positions"],

        "losing_positions": report["losing_positions"],

    }