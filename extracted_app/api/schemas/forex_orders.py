"""
api/schemas/forex_orders.py

Forex Order Request Schemas
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ForexOrderCreateRequest(BaseModel):

    pair: str = Field(..., description="e.g. 'EUR/USD' or 'EURUSD'")

    side: str = Field(..., description="'buy' or 'sell'")

    units: float | None = Field(default=None, gt=0, description="Notional units of base currency")

    lots: float | None = Field(default=None, gt=0, description="Standard lots (1 lot = 100,000 units) -- alternative to units")

    order_type: str = Field(default="MARKET", description="'MARKET', 'LIMIT', 'STOP', or 'STOP_LIMIT'")

    limit_price: float | None = Field(default=None, gt=0)

    stop_price: float | None = Field(default=None, gt=0)

    target_price: float | None = Field(default=None, gt=0)

    leverage: float | None = Field(default=None, gt=0)

    broker: str = Field(default="paper", description="'paper' for simulated fills; anything else routes through the live broker layer")

    portfolio_id: str | None = Field(
        default=None,
        description="Which forex portfolio this order applies to. Omit to use your default portfolio (auto-created on first use).",
    )