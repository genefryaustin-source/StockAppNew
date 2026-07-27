"""
Global Exception Handlers
"""

from __future__ import annotations

import logging
import traceback
from fastapi import FastAPI
from fastapi import Request
from fastapi.responses import JSONResponse

from api.exceptions.api_exceptions import APIException

logger = logging.getLogger(__name__)


def register_exception_handlers(
    app: FastAPI,
):

    @app.exception_handler(APIException)
    async def api_exception_handler(
        request: Request,
        exc: APIException,
    ):

        logger.warning(
            "%s %s -> %s",
            request.method,
            request.url.path,
            exc.error_code,
        )

        return JSONResponse(

            status_code=exc.status_code,

            content={

                "success": False,

                "request_id": getattr(
                    request.state,
                    "request_id",
                    None,
                ),

                "error": {

                    "code": exc.error_code,

                    "message": exc.message,

                    "details": exc.details,

                },

            },

        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request, exc):
        logger.exception("Unhandled exception")
        traceback.print_exc()

        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "request_id": getattr(request.state, "request_id", None),
                "error": {
                    "code": "internal_server_error",
                    "message": str(exc),  # TEMPORARY for debugging
                },
            },
        )