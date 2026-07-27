"""
StockApp Platform API

Application lifespan management.

Responsible for:

    • Startup initialization

    • Runtime validation

    • Database validation

    • Provider validation

    • Graceful shutdown

Business logic intentionally lives elsewhere.
"""

from __future__ import annotations

import logging
import os
import platform
import sys
import time

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from api.version import (
    API_VERSION,
    BUILD_NUMBER,
)

from api.config import settings

from api.services import register_services
from api.services import register_services



logger = logging.getLogger(__name__)

START_TIME = time.time()

async def startup():

    logger.info("Starting StockApp Platform API")

    register_services()

    logger.info("Services registered")
# ---------------------------------------------------------
# Startup Helpers
# ---------------------------------------------------------

def initialize_logging() -> None:
    """
    Configure application logging.
    """

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper()),
        format=(
            "%(asctime)s | "
            "%(levelname)-8s | "
            "%(name)s | "
            "%(message)s"
        ),
    )

    logger.info("Logging initialized")


def validate_environment() -> None:
    """
    Validate runtime environment.
    """

    logger.info("Environment: %s", settings.environment)
    logger.info("Python: %s", sys.version.split()[0])
    logger.info("Platform: %s", platform.platform())


def validate_database() -> bool:
    """
    Ensures every table this API depends on actually exists, by
    running the same table-creation step (modules.db.core.
    init_database(), which calls Base.metadata.create_all()) the
    Streamlit app runs on its own startup.

    Previously this only checked that DATABASE_URL was a non-empty
    string and never actually touched the database at all -- meaning
    this API has been silently depending on the separate Streamlit app
    (app.py) having already run init_database() against the same
    database at some point in the past. Any table added since the
    Streamlit process was last restarted (or, if it's never run
    against this database at all) would be missing here, surfacing as
    psycopg2.errors.UndefinedTable the first time an endpoint touched
    it -- not specific to any one table, but to every table this API
    uses, whenever this process is the first (or only) one to touch a
    given database.

    init_database() runs regardless of whether settings.database_url
    is set: modules.db.core has its own, independent SQLite-fallback
    connection logic that doesn't depend on this setting at all, so
    gating table creation on it would mean this API never creates its
    own tables for exactly the deployments relying on that fallback --
    the same bug this exists to close, just for a different case. The
    settings.database_url check here is informational only (did this
    API's own config get a real DATABASE_URL, or will the connection
    fall back to SQLite).

    Raises (rather than swallowing the error) if table creation
    itself fails -- an API that can silently start up without its own
    schema in place is far more confusing to debug later than one that
    fails loudly at boot.
    """

    if settings.database_url:
        logger.info("Database URL configured")
    else:
        logger.warning("DATABASE_URL not configured -- falling back to SQLite")

    from modules.db.core import init_database

    try:
        init_database()
    except Exception:
        logger.exception("Database initialization (table creation) failed.")
        raise

    logger.info("Database tables verified/created")

    return True


def validate_security() -> None:
    """
    Refuses to start outside development mode with a default/weak
    JWT_SECRET -- a token signed with a known placeholder secret
    (the app's own default is the literal string "CHANGE_ME") is
    forgeable by anyone, for any tenant_id and any permissions. Failing
    at startup means an operator finds out immediately, rather than
    silently running an app where JWT auth provides no real security
    until the first attacker (or the first security review) finds it.

    Exempt in development mode, the same as every other auth bypass in
    this app -- see api.auth.dependencies.get_current_user.
    """

    from api.auth.jwt import _ensure_secret_is_safe_to_use

    _ensure_secret_is_safe_to_use(settings.jwt_secret)

    logger.info("JWT secret configuration OK for environment: %s", settings.environment)


def initialize_runtime() -> None:
    """
    Placeholder for future runtime.

    Future Sprints

        Runtime Context

        Scheduler

        Worker Pool

        AI Runtime

        Provider Router

        Broker Router
    """

    logger.info("Runtime initialized")


def initialize_providers() -> None:
    """
    Placeholder.

    Future Sprint.
    """

    logger.info("Provider initialization complete")


def initialize_background_tasks() -> None:
    """
    Placeholder.

    Future Sprint.
    """

    if settings.enable_background_tasks:

        logger.info("Background tasks enabled")


# ---------------------------------------------------------
# Shutdown Helpers
# ---------------------------------------------------------

def shutdown_runtime() -> None:
    logger.info("Runtime shutdown complete")


def shutdown_providers() -> None:
    logger.info("Providers disconnected")


def shutdown_scheduler() -> None:
    logger.info("Scheduler stopped")


# ---------------------------------------------------------
# Lifespan
# ---------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    FastAPI lifespan handler.
    """

    logger.info("=" * 70)

    initialize_logging()

    logger.info("Starting StockApp Platform API")

    register_services()

    logger.info("Version: %s", API_VERSION)

    logger.info("Build: %s", BUILD_NUMBER)

    validate_environment()

    validate_database()

    validate_security()

    initialize_runtime()

    initialize_providers()

    initialize_background_tasks()

    logger.info("Startup complete")

    logger.info("=" * 70)

    yield

    logger.info("=" * 70)

    logger.info("Stopping StockApp Platform API")

    shutdown_scheduler()

    shutdown_runtime()

    shutdown_providers()

    elapsed = time.time() - START_TIME

    logger.info("Runtime %.2f seconds", elapsed)

    logger.info("Shutdown complete")

    logger.info("=" * 70)