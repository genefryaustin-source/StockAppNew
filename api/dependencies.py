"""
Dependency Injection

Central dependency providers used throughout
the Platform API.

Routers should never construct shared services
directly.

Instead they depend on these helpers.
"""

from __future__ import annotations

import logging
import uuid

from typing import Generator

from fastapi import Depends
from fastapi import Request

from api.config import (
    settings,
    Settings,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

def get_settings() -> Settings:
    """
    Returns the singleton settings object.
    """

    return settings


# ---------------------------------------------------------
# Request ID
# ---------------------------------------------------------

def get_request_id(
    request: Request,
) -> str:
    """
    Returns request ID.

    Middleware will overwrite this
    with a persistent value.
    """

    request_id = getattr(
        request.state,
        "request_id",
        None,
    )

    if request_id:

        return request_id

    request_id = str(uuid.uuid4())

    request.state.request_id = request_id

    return request_id


# ---------------------------------------------------------
# Logger
# ---------------------------------------------------------

def get_logger() -> logging.Logger:
    """
    Shared logger dependency.
    """

    return logger


# ---------------------------------------------------------
# Current User
# ---------------------------------------------------------
#
# Deliberately not re-exported here. The real implementation is
# api.auth.dependencies.get_current_user (handles the development
# bypass, JWT, and API keys) -- import it from api.auth directly.
# Re-exporting it here would create a circular import, since that
# function depends on get_db() below, which lives in this module.
#
# This used to be a second, separate, always-unauthenticated
# placeholder -- dangerous to leave in place, since importing
# get_current_user from here instead of api.auth would have silently
# produced a user that's never authenticated and has no permissions,
# with no error to catch the mistake. Removed rather than fixed in
# place, since nothing currently imports it from here.


# ---------------------------------------------------------
# Database
# ---------------------------------------------------------

def get_db() -> Generator:
    """
    Per-request SQLAlchemy session. Used by routers that need direct
    database access rather than going through module_registry (whose
    services share one session per service-key for the life of the
    process -- fine for most read-mostly endpoints, but auth is checked
    on every single request, so it gets its own fresh session instead
    of sharing that risk).
    """

    from modules.db.core import new_db_session

    db = new_db_session()

    try:

        yield db

    finally:

        db.close()


# ---------------------------------------------------------
# Common Dependency Bundle
# ---------------------------------------------------------

def common_dependencies(
    request_id: str = Depends(get_request_id),
    config: Settings = Depends(get_settings),
):
    """
    Frequently-used dependency bundle. Does not include current_user --
    add Depends(api.auth.get_current_user) directly to an endpoint that
    needs it, rather than through this bundle, which would create a
    circular import (api.auth.dependencies already depends on get_db()
    above).
    """

    return {

        "request_id": request_id,

        "config": config,

    }