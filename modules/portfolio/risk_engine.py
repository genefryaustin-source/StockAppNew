import streamlit as st


def validate_order(portfolio_value, position_value, order_notional, side):
    cfg = st.secrets.get("trading", {})

    max_notional = float(cfg.get("MAX_ORDER_NOTIONAL", 50000))
    max_position_pct = float(cfg.get("MAX_POSITION_PCT", 0.25))
    allow_shorts = bool(cfg.get("ALLOW_SHORTS", False))

    if order_notional > max_notional:
        return False, "Order exceeds max notional limit"

    if (position_value + order_notional) / portfolio_value > max_position_pct:
        return False, "Position size exceeds max allocation"

    if side == "sell" and not allow_shorts:
        return True, None  # handled by position check later

    return True, None