"""
Platform API Exceptions
"""

from __future__ import annotations


class APIException(Exception):

    status_code = 500

    error_code = "internal_error"

    message = "Internal Server Error"

    def __init__(
        self,
        message: str | None = None,
        details: dict | None = None,
    ):

        self.message = message or self.message

        self.details = details or {}

        super().__init__(self.message)


class BadRequest(APIException):

    status_code = 400

    error_code = "bad_request"

    message = "Bad Request"


class Unauthorized(APIException):

    status_code = 401

    error_code = "unauthorized"

    message = "Unauthorized"


class Forbidden(APIException):

    status_code = 403

    error_code = "forbidden"

    message = "Forbidden"


class NotFound(APIException):

    status_code = 404

    error_code = "not_found"

    message = "Resource Not Found"


class Conflict(APIException):

    status_code = 409

    error_code = "conflict"

    message = "Conflict"


class Validation(APIException):

    status_code = 422

    error_code = "validation_error"

    message = "Validation Error"


class TooManyRequests(APIException):

    status_code = 429

    error_code = "rate_limit"

    message = "Too Many Requests"


class InternalServerError(APIException):

    status_code = 500

    error_code = "internal_server_error"

    message = "Internal Server Error"