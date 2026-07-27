"""
StockApp Platform API

Production REST API for the StockApp platform.

This package exposes the StockApp services through
FastAPI while sharing the existing business logic,
repositories, providers, and analytics engines.

Streamlit UI:
    app.py

REST API:
    api.main

Author:
    Conduro Ventures

"""

from .version import (
    API_NAME,
    API_VERSION,
)

__all__ = [
    "API_NAME",
    "API_VERSION",
]