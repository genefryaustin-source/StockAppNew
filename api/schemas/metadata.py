from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class ResponseMetadata(BaseModel):

    request_id: str | None = None

    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC)
    )

    version: str

    processing_time_ms: float | None = None