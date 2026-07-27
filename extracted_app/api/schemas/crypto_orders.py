"""
api/schemas/crypto_orders.py

Crypto Order Request Schemas
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class CryptoOrderCreateRequest(BaseModel):

    portfolio_id: str = Field(..., min_length=1)

    symbol: str = Field(
        ..., min_length=3, max_length=20,
        description="ccxt-unified pair format, e.g. 'BTC/USDT' -- not the exchange-specific 'BTCUSDT'.",
    )

    side: str = Field(..., description="'buy' or 'sell'")

    qty: float = Field(..., gt=0, description="Amount of the base currency (e.g. 0.1 for 0.1 BTC).")

    order_type: str = Field(default="market", description="'market' or 'limit'")

    tif: str = Field(default="day")

    limit_price: float | None = Field(default=None, gt=0)

    stop_price: float | None = Field(default=None, gt=0)