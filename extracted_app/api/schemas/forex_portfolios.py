"""
api/schemas/forex_portfolios.py

Forex Portfolio Request Schemas
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ForexPortfolioCreateRequest(BaseModel):

    name: str = Field(..., min_length=1, max_length=150)

    description: str = Field(default="", max_length=2000)

    base_currency: str = Field(default="USD", max_length=10)

    starting_balance: float = Field(default=100000.0, gt=0)

    is_default: bool = Field(default=False)


class ForexPortfolioUpdateRequest(BaseModel):

    name: str = Field(..., min_length=1, max_length=150)

    description: str = Field(default="", max_length=2000)

    base_currency: str = Field(default="USD", max_length=10)

    status: str = Field(default="ACTIVE")