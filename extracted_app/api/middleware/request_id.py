"""
Request ID Middleware

Every request receives a unique identifier.

The request id is available in:

    request.state.request_id

and returned in

    X-Request-ID

response header.
"""

from __future__ import annotations

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RequestIDMiddleware(BaseHTTPMiddleware):

    async def dispatch(
        self,
        request: Request,
        call_next,
    ) -> Response:

        request_id = str(uuid.uuid4())

        request.state.request_id = request_id

        request.state.request_start = time.perf_counter()

        response = await call_next(request)

        response.headers["X-Request-ID"] = request_id

        return response