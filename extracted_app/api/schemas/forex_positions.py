"""
api/schemas/forex_positions.py

Forex Position Management Request Schemas
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ForexPositionCloseRequest(BaseModel):

    quantity: float | None = Field(
        default=None, gt=0,
        description="Units to close. Omit to close the full position.",
    )

    exit_price: float | None = Field(
        default=None, gt=0,
        description="Omit to use the current market price.",
    )


class ForexPositionModifyRequest(BaseModel):

    stop_price: float | None = Field(default=None, gt=0, description="Omit to leave unchanged.")

    target_price: float | None = Field(default=None, gt=0, description="Omit to leave unchanged.")


class ForexFlattenRequest(BaseModel):

    portfolio_id: str | None = Field(
        default=None,
        description="Which portfolio's account to flatten. Omit to use your default portfolio.",
    )