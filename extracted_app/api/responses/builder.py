from __future__ import annotations

from typing import Any

from fastapi import Request

from api.schemas.metadata import ResponseMetadata
from api.schemas.response import APIResponse
from api.version import API_VERSION


class ResponseBuilder:

    @staticmethod
    def success(
        *,
        request: Request,
        data: Any,
    ) -> APIResponse:

        return APIResponse(

            success=True,

            data=data,

            meta=ResponseMetadata(

                request_id=getattr(
                    request.state,
                    "request_id",
                    None,
                ),

                processing_time_ms=getattr(
                    request.state,
                    "process_time_ms",
                    None,
                ),

                version=API_VERSION,
            ),
        )

    @staticmethod
    def empty(
        *,
        request: Request,
    ) -> APIResponse:

        return APIResponse(

            success=True,

            data=None,

            meta=ResponseMetadata(

                request_id=getattr(
                    request.state,
                    "request_id",
                    None,
                ),

                processing_time_ms=getattr(
                    request.state,
                    "process_time_ms",
                    None,
                ),

                version=API_VERSION,
            ),
        )
    @staticmethod
    def created(
        *,
        request: Request,
        data: Any,
    ) -> APIResponse:

        return ResponseBuilder.success(
            request=request,
            data=data,
        )