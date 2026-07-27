"""
api/auth/entitlements.py

Entitlements

Concepts surfaced in the login response (api/routers/auth.py) and
re-checked server-side wherever they matter, not just handed to the
client as a hint:

    platform     Which version of this API/response contract the
                 client is talking to (api.version.MOBILE_API_VERSION,
                 API_VERSION, BUILD_NUMBER) -- lets a client detect a
                 shape it doesn't understand yet rather than assume.

    capabilities Wraps modules + permissions with its own schema
                 version (api.version.CAPABILITIES_SCHEMA_VERSION),
                 separate from the platform version above, since this
                 block's own shape can evolve on its own schedule.

    modules      Tenant-level asset-class licensing (modules.db.models.
                 Tenant.module_*_enabled). Rarely changes during a
                 session -- this is "does this organization have a
                 Forex license at all", set by a super admin, not a
                 per-request permission check. Each enabled module
                 reports its own capability-contract version
                 (api.version.MODULE_VERSIONS) so module-specific
                 fields can be added later (e.g. forex gaining
                 "brokers"/"live_trading") without changing the
                 response's overall shape or requiring every client to
                 update at once.

    permissions  A small, mobile-UI-friendly summary derived from the
                 same granular permission catalog (api.auth.
                 permissions.PERMISSIONS) that every endpoint's
                 require_permission() actually enforces -- not a
                 second, parallel permission system. If the underlying
                 catalog changes, this derivation should be revisited,
                 but there is deliberately only one source of truth
                 for what a user can actually do.

get_modules_for_tenant() (the rich, client-facing shape) is
deliberately separate from get_module_flags_for_tenant() (plain
booleans): server-side enforcement code (api.services.
executive_mobile_dashboard_api_service) needs a simple bool per
module, not to unwrap {"enabled": ...} everywhere it checks one.
"""

from __future__ import annotations

from api.version import (
    API_VERSION,
    BUILD_NUMBER,
    MOBILE_API_VERSION,
    CAPABILITIES_SCHEMA_VERSION,
    MODULE_VERSIONS,
)


def get_module_flags_for_tenant(tenant) -> dict[str, bool]:
    """
    Plain booleans, for server-side enforcement (api.services.
    executive_mobile_dashboard_api_service checks these directly --
    e.g. `if flags["forex"]:`). tenant is a modules.db.models.Tenant
    row (or anything with these four attributes). Reported honestly:
    crypto defaults False because there is no trading capability
    behind it at all yet, not because of a licensing decision -- see
    the long comment on these columns in modules/db/models.py.
    """
    return {
        "stocks": bool(getattr(tenant, "module_stocks_enabled", True)),
        "options": bool(getattr(tenant, "module_options_enabled", True)),
        "forex": bool(getattr(tenant, "module_forex_enabled", True)),
        "crypto": bool(getattr(tenant, "module_crypto_enabled", False)),
    }


def get_modules_for_tenant(tenant) -> dict[str, dict]:
    """
    The client-facing "capabilities.modules" shape: each module is an
    object, not a bare boolean, specifically so module-specific fields
    can be added later (paper_trading, live_trading, brokers, ...)
    without changing the response's overall shape -- a client parsing
    module.enabled today keeps working unchanged the day a field gets
    added next to it. A disabled module reports only {"enabled":
    false} -- no version, since there's nothing versioned to report
    for a module the caller can't use.
    """
    flags = get_module_flags_for_tenant(tenant)

    modules: dict[str, dict] = {}
    for name, enabled in flags.items():
        if enabled and name in MODULE_VERSIONS:
            modules[name] = {"enabled": True, "version": MODULE_VERSIONS[name]}
        else:
            modules[name] = {"enabled": enabled}

    return modules


def get_permissions_summary(
    *,
    permissions: list[str],
    is_super_admin: bool,
) -> dict[str, bool]:
    """
    Coarse, mobile-friendly capability flags derived from the same
    granular permission set require_permission() checks -- this is a
    read-only summary for client-side UI decisions (e.g. "show the
    live-trading toggle"), not an independent grant of access.
    """

    def has(permission: str) -> bool:
        return is_super_admin or permission in permissions

    return {
        "paper_trade": is_super_admin or any(
            has(p) for p in ("stocks.write", "options.write", "forex.write")
        ),
        # No live trading path exists anywhere on this platform today
        # (every order execution service in this build is a paper
        # broker) -- reported False for everyone rather than implying
        # a capability that doesn't exist.
        "live_trade": False,
        "analytics": has("analytics.read"),
        # executive.read is what actually gates provider-health data
        # today (api/routers/executive.py's "providers" section) --
        # there is no separate provider_health permission in the
        # catalog, so this reflects the real check rather than
        # inventing a second one that would need to be kept in sync.
        "provider_health": has("executive.read"),
        "admin": is_super_admin or any(p.startswith("admin.") for p in permissions),
    }


def get_platform_info() -> dict:
    """The "platform" block: which API build/contract version the client is talking to."""
    return {
        "version": API_VERSION,
        "mobile_api": MOBILE_API_VERSION,
        "build": BUILD_NUMBER,
    }


def get_capabilities(
    *,
    tenant,
    permissions: list[str],
    is_super_admin: bool,
) -> dict:
    """The "capabilities" block: modules + permissions, with its own schema version."""
    return {
        "version": CAPABILITIES_SCHEMA_VERSION,
        "modules": get_modules_for_tenant(tenant),
        "permissions": get_permissions_summary(permissions=permissions, is_super_admin=is_super_admin),
    }