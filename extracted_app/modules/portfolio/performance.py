from modules.market_data.service import get_price_history
def calculate_portfolio_value(positions, prices):

    rows = []

    total_value = 0
    total_cost = 0

    for p in positions:

        symbol = p["symbol"]
        shares = float(p["quantity"])
        cost_basis = float(p["cost_basis"])

        price = prices.get(symbol, 0)

        value = shares * price
        cost = shares * cost_basis

        pnl = value - cost

        rows.append({
            "symbol": symbol,
            "shares": shares,
            "price": price,
            "value": value,
            "cost": cost,
            "pnl": pnl
        })

        total_value += value
        total_cost += cost

    total_pnl = total_value - total_cost

    return rows, total_value, total_cost, total_pnl