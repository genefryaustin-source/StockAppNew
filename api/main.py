"""
StockApp Platform API

Main FastAPI application.

This application hosts the REST API for every
StockApp platform module including:

    Stocks
    Options
    Forex
    Crypto
    Portfolio
    Trading
    AI
    Analytics

The API intentionally contains NO business logic.

Routers

↓

Platform Services

↓

Existing Modules

↓

Repositories

↓

Database

"""

from __future__ import annotations

import logging



from fastapi import FastAPI, Request

from fastapi.responses import JSONResponse
from api.lifespan import lifespan

from api.version import (
    API_NAME,
    API_DESCRIPTION,
    API_VERSION,
)

from api.config import settings


from api.middleware import (
    register_cors,
    ProcessTimeMiddleware,
    RequestIDMiddleware,
    RequestLoggingMiddleware,
    SecurityHeadersMiddleware,
    RateLimitMiddleware,
)

from api.exceptions import register_exception_handlers
from api.routers import api_router




logger = logging.getLogger(__name__)




# -----------------------------------------------------
# FastAPI
# -----------------------------------------------------

app = FastAPI(
    title=API_NAME,
    version=API_VERSION,
    description=API_DESCRIPTION,
    lifespan=lifespan,
    docs_url="/api/v1/docs" if settings.enable_docs else None,
    redoc_url="/api/v1/redoc" if settings.enable_redoc else None,
    openapi_url="/api/v1/openapi.json" if settings.enable_openapi else None,
    openapi_tags=[
        {
            "name": "Platform",
            "description": "Platform infrastructure endpoints",
        },
    ],
)

register_exception_handlers(app)
# -----------------------------------------------------
# Middleware
# -----------------------------------------------------

register_cors(app)

app.add_middleware(
    RequestIDMiddleware,
)

app.add_middleware(
    ProcessTimeMiddleware,
)

app.add_middleware(
    RequestLoggingMiddleware,
)

app.add_middleware(
    SecurityHeadersMiddleware,
)

app.add_middleware(
    RateLimitMiddleware,
)

app.include_router(api_router)



@app.get("/")
async def root():

    return {

        "application": "StockApp Platform API",

        "docs": "/docs",

        "redoc": "/redoc",

    }