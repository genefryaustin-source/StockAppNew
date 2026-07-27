"""
StockApp Platform API

Version Information
"""

from __future__ import annotations

from datetime import datetime

# ---------------------------------------------------------
# Platform
# ---------------------------------------------------------

PLATFORM_NAME = "StockApp"

COMPANY_NAME = "Conduro Ventures"

# ---------------------------------------------------------
# API
# ---------------------------------------------------------

API_NAME = "StockApp Platform API"

API_VERSION = "1.0.0"

API_MAJOR = 1

API_MINOR = 0

API_PATCH = 0

API_STAGE = "Development"

# ---------------------------------------------------------
# Build
# ---------------------------------------------------------

BUILD_DATE = datetime.utcnow().strftime("%Y-%m-%d")

BUILD_NUMBER = "2026.07.16"

# ---------------------------------------------------------
# Mobile API / Capabilities
# ---------------------------------------------------------
#
# Distinct from API_VERSION above (the overall REST API's semver):
# this tracks the login/refresh/me response *contract* specifically
# (api/routers/auth.py's "platform" and "capabilities" blocks) -- a
# mobile client can check this instead of parsing API_VERSION's semver
# to decide whether it understands the shape it just received. Bump
# MOBILE_API_VERSION when that response shape itself changes in a way
# a client needs to know about; CAPABILITIES_SCHEMA_VERSION when just
# the "capabilities" block's own shape changes (modules/permissions),
# since those can evolve independently of the rest of the response.
MOBILE_API_VERSION = 1

CAPABILITIES_SCHEMA_VERSION = 1

# Per-module capability-contract version -- bump a module's own entry
# when that module's fields inside "capabilities.modules" change
# shape (e.g. forex gaining "brokers"/"live_trading" fields), without
# needing to bump MOBILE_API_VERSION or affect any other module's
# clients. Only listed here for modules that actually exist -- crypto
# has no version because it has no capability contract yet (see
# api.auth.entitlements.get_modules_for_tenant).
MODULE_VERSIONS = {
    "stocks": 1,
    "options": 1,
    "forex": 1,
}

API_DESCRIPTION = """
Production REST API for the StockApp platform.

Provides secure access to:

• Stocks

• Options

• Forex

• Crypto

• Portfolio Management

• Trading

• AI Analytics

• Recommendations

• Institutional Research

• Market Data
"""

# ---------------------------------------------------------
# URLs
# ---------------------------------------------------------

DOCUMENTATION_URL = "/docs"

REDOC_URL = "/redoc"

OPENAPI_URL = "/openapi.json"