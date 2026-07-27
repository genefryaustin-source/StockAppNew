"""
CORS Middleware Registration

Registers the Starlette CORSMiddleware using the
centralized API configuration.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import settings


def register_cors(app: FastAPI) -> None:
    """
    Register Cross-Origin Resource Sharing middleware.
    """

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=settings.allowed_methods,
        allow_headers=settings.allowed_headers,
    )