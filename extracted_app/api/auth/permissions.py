"""
Permission Framework

Provides reusable authorization checks for the
StockApp Platform API.

This module is intentionally independent of JWT,
API keys, or the database.

Authentication identifies the caller.

Authorization determines what the caller may do.
"""

from __future__ import annotations

from collections.abc import Iterable

from fastapi import Depends

from api.auth.current_user import get_current_user
from api.auth.models import AuthenticatedUser
from api.exceptions import Forbidden


# ---------------------------------------------------------
# Permission Catalog
# ---------------------------------------------------------

PERMISSIONS = {

    #
    # Market Data
    #

    "market.read",

    #
    # Stocks
    #

    "stocks.read",
    "stocks.write",

    #
    # Options
    #

    "options.read",
    "options.write",

    #
    # Forex
    #

    "forex.read",
    "forex.write",

    #
    # Crypto
    #

    "crypto.read",
    "crypto.write",

    #
    # Portfolio
    #

    "portfolio.read",
    "portfolio.write",

    #
    # Trading
    #

    "orders.read",
    "orders.write",

    "positions.read",
    "positions.write",

    "execution.read",
    "execution.write",

    #
    # AI
    #

    "recommendations.read",
    "recommendations.write",

    "analytics.read",
    "analytics.write",

    "alerts.read",
    "alerts.write",

    "ipo.read",
    "preipo.read",

    "executive.read",

    "ai.read",

    #
    # Administration
    #

    "admin.system",
    "admin.users",
    "admin.tenants",
    "admin.api_keys",

}

# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def has_permission(
    user: AuthenticatedUser,
    permission: str,
) -> bool:
    """
    Returns True if the user has the requested permission.
    """

    if user.is_super_admin:
        return True

    return permission in user.permissions

def has_any_permission(
    user: AuthenticatedUser,
    permissions: Iterable[str],
) -> bool:

    if user.is_super_admin:
        return True

    return any(
        permission in user.permissions
        for permission in permissions
    )
def has_all_permissions(
    user: AuthenticatedUser,
    permissions: Iterable[str],
) -> bool:

    if user.is_super_admin:
        return True

    return all(
        permission in user.permissions
        for permission in permissions
    )
# ---------------------------------------------------------
# Dependency
# ---------------------------------------------------------

def require_permission(
    permission: str,
):
    """
    FastAPI dependency.

    Example

        Depends(
            require_permission(
                "portfolio.read"
            )
        )
    """

    def dependency(
        current_user: AuthenticatedUser = Depends(
            get_current_user,
        ),
    ) -> AuthenticatedUser:

        if not has_permission(
            current_user,
            permission,
        ):

            raise Forbidden(
                f"Permission required: {permission}",
                details={
                    "required_permission": permission,
                },
            )

        return current_user

    return dependency
def require_any_permission(
    permissions: Iterable[str],
):
    """
    Require at least one permission.
    """

    def dependency(
        current_user: AuthenticatedUser = Depends(
            get_current_user,
        ),
    ) -> AuthenticatedUser:

        if not has_any_permission(
            current_user,
            permissions,
        ):

            raise Forbidden(
                "Insufficient permissions.",
                details={
                    "required": list(permissions),
                },
            )

        return current_user

    return dependency
def require_all_permissions(
    permissions: Iterable[str],
):
    """
    Require every listed permission.
    """

    def dependency(
        current_user: AuthenticatedUser = Depends(
            get_current_user,
        ),
    ) -> AuthenticatedUser:

        if not has_all_permissions(
            current_user,
            permissions,
        ):

            raise Forbidden(
                "Missing required permissions.",
                details={
                    "required": list(permissions),
                },
            )

        return current_user

    return dependency