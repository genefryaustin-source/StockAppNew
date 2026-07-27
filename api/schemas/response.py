from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from .metadata import ResponseMetadata
from .pagination import PaginationMetadata


class APIResponse(BaseModel):

    success: bool = True

    data: Any = None

    meta: ResponseMetadata


class PaginatedResponse(APIResponse):

    pagination: PaginationMetadata


class ErrorBody(BaseModel):

    code: str

    message: str

    details: dict | None = None


class ErrorResponse(BaseModel):

    success: bool = False

    error: ErrorBody

    meta: ResponseMetadata