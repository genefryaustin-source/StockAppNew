"""
api/schemas/orders.py

Order Request Schemas

Pydantic request bodies for POST /api/v1/orders and
POST /api/v1/orders/{id}/replace.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class OrderCreateRequest(BaseModel):

    portfolio_id: str

    symbol: str = Field(..., min_length=1, max_length=20)

    side: str = Field(..., description="'buy' or 'sell'")

    qty: float = Field(..., gt=0)

    order_type: str = Field(default="market", description="'market', 'limit', or 'stop'")

    tif: str = Field(default="day")

    limit_price: float | None = Field(default=None, gt=0)

    stop_price: float | None = Field(default=None, gt=0)

    recommendation_id: int | None = None


class OrderReplaceRequest(BaseModel):
    """
    Partial replace -- only fields provided are changed. Only meaningful
    for an order that hasn't reached a terminal state yet; see
    OrdersAPIService.replace_order for why that's currently always the
    case for stock orders specifically.
    """

    qty: float | None = Field(default=None, gt=0)

    limit_price: float | None = Field(default=None, gt=0)

    stop_price: float | None = Field(default=None, gt=0)
    