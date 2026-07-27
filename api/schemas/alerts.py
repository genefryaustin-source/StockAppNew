"""
api/schemas/alerts.py

Alert Request Schemas
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class AlertCreateRequest(BaseModel):

    symbol: str = Field(..., min_length=1, max_length=20)

    title: str = Field(..., min_length=1, max_length=200)

    alert_type: str = Field(default="general", max_length=50)

    message: str = Field(default="", max_length=2000)