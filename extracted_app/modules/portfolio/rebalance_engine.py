import pandas as pd


def compute_rebalance(current_positions, target_weights, portfolio_value, price_map):

    trades = []

    for _, row in target_weights.iterrows():

        sym = row["symbol"]
        weight = row["weight"]

        price = price_map.get(sym)
        if not price or price <= 0:
            continue

        # Target position
        target_value = portfolio_value * weight

        # Current position (convert qty → value)
        current_qty = current_positions.get(sym, 0)
        current_value = current_qty * price

        diff_value = target_value - current_value

        # Ignore tiny noise
        if abs(diff_value) < portfolio_value * 0.01:
            continue

        side = "buy" if diff_value > 0 else "sell"

        qty = abs(diff_value) / price

        trades.append({
            "symbol": sym,
            "side": side,
            "qty": round(qty, 2),
            "price": price,
            "target_value": target_value,
            "current_value": current_value,
            "trade_value": diff_value,
        })

    return pd.DataFrame(trades)