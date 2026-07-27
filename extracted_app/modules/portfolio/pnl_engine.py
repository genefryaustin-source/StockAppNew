from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class FillCostResult:
    commission: float
    slippage: float
    total_cost: float


def estimate_transaction_cost(
    qty: float,
    reference_price: float,
    fill_price: float,
    commission_per_order: float = 0.0,
    min_commission: float = 0.0,
) -> FillCostResult:
    notional = abs(qty) * float(reference_price)
    commission = max(float(commission_per_order), float(min_commission))
    slippage = abs(qty) * abs(float(fill_price) - float(reference_price))
    total_cost = commission + slippage
    return FillCostResult(
        commission=commission,
        slippage=slippage,
        total_cost=total_cost,
    )


def update_position_after_fill(position_qty: float, position_avg_cost: float, fill_side: str, fill_qty: float, fill_price: float):
    signed_fill = fill_qty if fill_side.lower() == "buy" else -fill_qty
    new_qty = position_qty + signed_fill

    realized_pnl = 0.0
    new_avg_cost = position_avg_cost

    if position_qty == 0:
        new_avg_cost = fill_price
        return new_qty, new_avg_cost, realized_pnl

    if position_qty > 0 and signed_fill > 0:
        new_avg_cost = ((position_qty * position_avg_cost) + (fill_qty * fill_price)) / new_qty
    elif position_qty < 0 and signed_fill < 0:
        new_avg_cost = ((abs(position_qty) * position_avg_cost) + (fill_qty * fill_price)) / abs(new_qty)
    else:
        closing_qty = min(abs(position_qty), abs(fill_qty))
        if position_qty > 0:
            realized_pnl = closing_qty * (fill_price - position_avg_cost)
        else:
            realized_pnl = closing_qty * (position_avg_cost - fill_price)

        if new_qty == 0:
            new_avg_cost = 0.0
        elif (position_qty > 0 and new_qty < 0) or (position_qty < 0 and new_qty > 0):
            new_avg_cost = fill_price

    return new_qty, new_avg_cost, realized_pnl


def mark_to_market(qty: float, avg_cost: float, market_price: float) -> float:
    if qty > 0:
        return qty * (market_price - avg_cost)
    if qty < 0:
        return abs(qty) * (avg_cost - market_price)
    return 0.0

def closing_trade_metrics(
    prior_qty: float,
    prior_avg_cost: float,
    fill_side: str,
    fill_qty: float,
    fill_price: float,
    commission: float = 0.0,
    slippage: float = 0.0,
):
    """
    Returns None when no position-closing event occurred.
    Returns closed-trade metrics when the fill reduces or closes an existing position.
    """
    fill_side = (fill_side or "").lower()
    closed_qty = 0.0
    gross_pnl = 0.0
    side_open = None
    side_close = None

    if prior_qty > 0 and fill_side == "sell":
        closed_qty = min(abs(prior_qty), abs(fill_qty))
        gross_pnl = closed_qty * (float(fill_price) - float(prior_avg_cost))
        side_open = "buy"
        side_close = "sell"

    elif prior_qty < 0 and fill_side == "buy":
        closed_qty = min(abs(prior_qty), abs(fill_qty))
        gross_pnl = closed_qty * (float(prior_avg_cost) - float(fill_price))
        side_open = "sell"
        side_close = "buy"

    if closed_qty <= 0:
        return None

    total_cost = float(commission or 0.0) + float(slippage or 0.0)
    net_pnl = gross_pnl - total_cost

    return {
        "closed_qty": float(closed_qty),
        "gross_pnl": float(gross_pnl),
        "net_pnl": float(net_pnl),
        "side_open": side_open,
        "side_close": side_close,
    }