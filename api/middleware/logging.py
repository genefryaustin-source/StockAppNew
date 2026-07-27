"""
Structured Request Logging Middleware

Logs every request entering the Platform API.

Future versions will persist logs to:

    api_request_log

and integrate with

    Platform Activity

    Runtime Dashboard

    Provider Telemetry

    Execution Analytics
"""

from __future__ import annotations

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("stockapp.api")


class RequestLoggingMiddleware(BaseHTTPMiddleware):

    async def dispatch(
        self,
        request: Request,
        call_next,
    ) -> Response:

        start = time.perf_counter()

        response = await call_next(request)

        elapsed = getattr(
            request.state,
            "process_time_ms",
            None,
        )

        if elapsed is None:
            elapsed = (
                              time.perf_counter() - start
                      ) * 1000

        request_id = getattr(
            request.state,
            "request_id",
            "-"
        )

        logger.info(
            (
                "[%s] %s %s -> %s %.2f ms"
            ),
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            elapsed,
        )

        return response