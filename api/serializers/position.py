from __future__ import annotations

from typing import Any


def serialize_position(position: Any) -> dict:
    """
    Convert a PortfolioPosition ORM model into
    a JSON-serializable dictionary.
    """

    return {
        "symbol": position.symbol,
        "qty": position.qty,
        "avg_cost": position.avg_cost,
        "market_price": position.market_price,
        "market_value": position.market_value,
        "unrealized_pnl": position.unrealized_pnl,
        "realized_pnl": position.realized_pnl,
        "updated_at": (
            position.updated_at.isoformat()
            if position.updated_at
            else None
        ),
    }


def serialize_positions(positions: list[Any]) -> list[dict]:
    """
    Serialize a list of PortfolioPosition objects.
    """

    return [
        serialize_position(position)
        for position in positions
    ]