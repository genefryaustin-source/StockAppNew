"""
Request Timing Middleware

Measures request execution time.

Adds:

    X-Process-Time

response header.

Stores timing information on the request state for
future logging, metrics, and analytics.
"""

from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class ProcessTimeMiddleware(BaseHTTPMiddleware):
    """
    Measure request execution time.
    """

    async def dispatch(
        self,
        request: Request,
        call_next,
    ) -> Response:

        start = time.perf_counter()

        response = await call_next(request)

        elapsed = time.perf_counter() - start

        elapsed_ms = elapsed * 1000.0

        request.state.process_time_seconds = elapsed
        request.state.process_time_ms = elapsed_ms

        response.headers["X-Process-Time"] = f"{elapsed_ms:.3f} ms"

        return response