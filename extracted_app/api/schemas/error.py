"""
Error Response Schemas
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel
from pydantic import Field


class ErrorDetail(BaseModel):

    code: str

    message: str

    details: dict | None = None


class ErrorResponse(BaseModel):

    success: bool = False

    timestamp: datetime = Field(default_factory=datetime.utcnow)

    request_id: str | None = None

    error: ErrorDetail