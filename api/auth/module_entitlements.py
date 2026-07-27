"""
api/auth/module_entitlements.py

Module Entitlement Enforcement

A FastAPI dependency, parallel to api.auth.permissions.
require_permission, but for tenant-level asset-class licensing
(modules.db.models.Tenant.module_*_enabled) rather than user-level
permissions.

This is the gap that made the earlier "will crypto trades be blocked
if this tenant only pays for crypto" question worth checking directly:
before this, nothing outside GET /api/v1/executive/mobile-dashboard's
own read-only summary ever checked a tenant's module entitlements at
all -- every actual order-submission endpoint (stocks, options, forex,
crypto) would place a trade for any authenticated, permitted user
regardless of what modules their tenant is actually licensed for.
Confirmed directly: a tenant configured with module_stocks_enabled=
False could still submit a real stock order with nothing rejecting it
except an unrelated data-availability failure.

require_permission answers "can this user do this kind of thing at
all"; require_module answers "is this tenant's organization licensed
for this asset class" -- both are checked, independently, on every
order-submission endpoint now.
"""

from __future__ import annotations

from fastapi import Depends

from api.auth import get_current_user
from api.auth.models import AuthenticatedUser
from api.dependencies import get_db
from api.exceptions import Forbidden


def require_module(module_name: str):
    """
    FastAPI dependency. module_name must be one of "stocks", "options",
    "forex", "crypto" (api.auth.entitlements.get_module_flags_for_tenant's
    keys). A super admin bypasses this the same way they bypass every
    permission check -- module licensing is a tenant-level concern, not
    something that should block platform-level administration.

    Example

        Depends(
            require_module("crypto")
        )
    """

    def dependency(
        current_user: AuthenticatedUser = Depends(
            get_current_user,
        ),
        db=Depends(get_db),
    ) -> AuthenticatedUser:

        if current_user.is_super_admin:
            return current_user

        from modules.db.models import Tenant
        from api.auth.entitlements import get_module_flags_for_tenant

        tenant = None
        if current_user.tenant_id:
            try:
                tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).one_or_none()
            except Exception:
                try:
                    db.rollback()
                except Exception:
                    pass
                tenant = None

        # No tenant row found -- get_module_flags_for_tenant's own
        # getattr(tenant, ..., default) defaults match new-column
        # defaults (stocks/options/forex True, crypto False), so a
        # missing tenant row degrades to those same defaults rather
        # than blocking every request over a lookup miss.
        flags = get_module_flags_for_tenant(tenant)

        if not flags.get(module_name, False):
            raise Forbidden(
                f"This tenant is not licensed for {module_name}. Contact your administrator.",
                details={
                    "required_module": module_name,
                },
            )

        return current_user

    return dependency