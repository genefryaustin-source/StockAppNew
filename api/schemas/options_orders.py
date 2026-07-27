"""
api/schemas/options_orders.py

Options Order Request Schemas
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class OptionsOrderCreateRequest(BaseModel):

    option_symbol: str = Field(..., min_length=1, max_length=40)

    qty: int = Field(..., gt=0)

    side: str = Field(..., description="'buy' or 'sell'")

    position_intent: str = Field(
        default="buy_to_open",
        description="'buy_to_open', 'buy_to_close', 'sell_to_open', or 'sell_to_close'",
    )

    order_type: str = Field(default="limit", description="'market' or 'limit'")

    tif: str = Field(default="day")

    limit_price: float | None = Field(default=None, gt=0)