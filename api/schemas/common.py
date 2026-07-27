"""
Common API Schemas
"""

from __future__ import annotations

from datetime import datetime

from typing import Any

from pydantic import BaseModel
from pydantic import Field


class ApiResponse(BaseModel):

    success: bool = True

    timestamp: datetime = Field(default_factory=datetime.utcnow)

    request_id: str | None = None

    data: Any = None