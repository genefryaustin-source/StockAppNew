"""
modules/admin/tenant_service.py

Tenant Service

CRUD for the Tenant row itself: list, get, create, rename, activate,
deactivate, and the external-platform-API-access gate (see
api.auth.api_keys.APIKeyService._tenant_has_api_access).

Every method here trusts its caller to have already checked the
requester's role -- this service does not enforce who's allowed to
call it. Both modules/admin/tenant_admin_ui.py (Streamlit) and
api/routers/admin_tenants.py (REST, gated on the "admin.tenants"
permission) call this directly.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import text

logger = logging.getLogger(__name__)


def _safe_rollback(db) -> None:
    """
    Roll back after a caught DB-touching exception. On Postgres, one
    failed query leaves the whole transaction aborted -- every
    subsequent command on that same session is refused until a
    rollback happens, not just the one that failed. This service's
    session is cached and reused across every request to whichever
    endpoint calls it for the life of the process, so skipping this
    doesn't just break the current request -- it breaks every request
    after it until the process restarts. Never raises.
    """
    try:
        db.rollback()
    except Exception:
        logger.exception("Rollback itself failed -- session may be unusable.")


class TenantService:

    def __init__(self, db):
        self.db = db

    def list_tenants(self):
        """
        Every tenant, alphabetical by name. Returns [] (not an
        exception) on a database error.
        """

        _safe_rollback(self.db)

        try:
            rows = self.db.execute(
                text("""
                       SELECT
                           id,
                           name,
                           is_active,
                           created_at,
                           platform_api_access_enabled
                       FROM tenants
                       ORDER BY name
                   """)
            )

            return [
                {
                    "id": r[0],
                    "name": r[1],
                    "is_active": bool(r[2]),
                    "created_at": r[3],
                    "platform_api_access_enabled": bool(r[4]),
                }
                for r in rows
            ]

        except Exception:
            logger.exception("Failed to list tenants.")
            _safe_rollback(self.db)
            return []

    def get_tenant(self, tenant_id: str) -> dict | None:
        """
        Single tenant by id. Returns None (not an exception) if it
        doesn't exist or on a database error.
        """

        _safe_rollback(self.db)

        try:
            row = self.db.execute(
                text("""
                       SELECT
                           id,
                           name,
                           is_active,
                           created_at,
                           platform_api_access_enabled
                       FROM tenants
                       WHERE id = :id
                   """),
                {"id": tenant_id},
            ).fetchone()

        except Exception:
            logger.exception("Failed to fetch tenant | tenant_id=%s", tenant_id)
            _safe_rollback(self.db)
            return None

        if row is None:
            return None

        return {
            "id": row[0],
            "name": row[1],
            "is_active": bool(row[2]),
            "created_at": row[3],
            "platform_api_access_enabled": bool(row[4]),
        }

    def create_tenant(self, name: str, platform_api_access_enabled: bool = False):
        """
        platform_api_access_enabled defaults to False -- a newly created
        tenant has no external API access until a super admin explicitly
        turns it on (here, at creation time, or later via
        set_platform_api_access). This is the "as part of setting up a
        tenant" gate: creating a tenant does not by itself grant it
        access to create or use api.auth.api_keys.PlatformAPIKey keys.

        Returns the new tenant's id, or None (not an exception) on a
        database error.
        """

        _safe_rollback(self.db)

        tenant_id = str(uuid.uuid4())

        try:
            self.db.execute(text("""
                INSERT INTO tenants (
                    id,
                    name,
                    is_active,
                    created_at,
                    platform_api_access_enabled
                )
                VALUES (
                    :id,
                    :name,
                    TRUE,
                    CURRENT_TIMESTAMP,
                    :api_access
                )
            """), {
                "id": tenant_id,
                "name": name,
                "api_access": platform_api_access_enabled,
            })

            self.db.commit()

        except Exception:
            logger.exception("Failed to create tenant | name=%s", name)
            _safe_rollback(self.db)
            return None

        return tenant_id

    def update_tenant(self, tenant_id: str, name: str) -> bool:
        """
        Rename a tenant. Returns True/False rather than raising -- False
        for either a database error or a tenant_id that doesn't exist
        (an UPDATE matching zero rows isn't itself an error to SQL, so
        this checks rowcount rather than trusting a lack of exception).
        """

        _safe_rollback(self.db)

        try:
            result = self.db.execute(text("""
                UPDATE tenants
                SET name = :name
                WHERE id = :id
            """), {
                "id": tenant_id,
                "name": name,
            })

            self.db.commit()
            return result.rowcount > 0

        except Exception:
            logger.exception("Failed to update tenant | tenant_id=%s", tenant_id)
            _safe_rollback(self.db)
            return False

    def deactivate_tenant(self, tenant_id: str) -> bool:
        _safe_rollback(self.db)

        try:
            result = self.db.execute(text("""
                UPDATE tenants
                SET is_active = FALSE
                WHERE id = :id
            """), {"id": tenant_id})

            self.db.commit()
            return result.rowcount > 0

        except Exception:
            logger.exception("Failed to deactivate tenant | tenant_id=%s", tenant_id)
            _safe_rollback(self.db)
            return False

    def activate_tenant(self, tenant_id: str) -> bool:
        _safe_rollback(self.db)

        try:
            result = self.db.execute(text("""
                UPDATE tenants
                SET is_active = TRUE
                WHERE id = :id
            """), {"id": tenant_id})

            self.db.commit()
            return result.rowcount > 0

        except Exception:
            logger.exception("Failed to activate tenant | tenant_id=%s", tenant_id)
            _safe_rollback(self.db)
            return False

    # ------------------------------------------------------------
    # External platform API access gate
    # ------------------------------------------------------------
    #
    # Super-admin only -- enforced by the caller (the UI/router that
    # calls this), not by this method itself, the same way every other
    # method here trusts its caller to have already checked the
    # requester's role. This is what api.auth.api_keys.APIKeyService
    # checks both when a new key is created for a tenant and every
    # time an existing key authenticates, so flipping this off here
    # takes effect immediately -- not just for new keys.

    def set_platform_api_access(self, tenant_id: str, enabled: bool) -> bool:
        _safe_rollback(self.db)

        try:
            result = self.db.execute(text("""
                UPDATE tenants
                SET platform_api_access_enabled = :enabled
                WHERE id = :id
            """), {"id": tenant_id, "enabled": enabled})

            self.db.commit()
            return result.rowcount > 0

        except Exception:
            logger.exception(
                "Failed to set platform API access | tenant_id=%s", tenant_id
            )
            _safe_rollback(self.db)
            return False

    def get_platform_api_access(self, tenant_id: str) -> bool:
        _safe_rollback(self.db)

        try:
            row = self.db.execute(text("""
                SELECT platform_api_access_enabled
                FROM tenants
                WHERE id = :id
            """), {"id": tenant_id}).fetchone()

            return bool(row[0]) if row is not None else False

        except Exception:
            logger.exception(
                "Failed to read platform API access | tenant_id=%s", tenant_id
            )
            _safe_rollback(self.db)
            return False

    # Column names for the four module entitlement flags on Tenant
    # (modules/db/models.py) -- keyed by the short name used in the API
    # (api.auth.entitlements.get_modules_for_tenant, the login response's
    # "modules" block, and GET /api/v1/executive/mobile-dashboard's
    # server-side enforcement), so callers pass "forex", not the raw
    # column name.
    MODULE_COLUMNS = {
        "stocks": "module_stocks_enabled",
        "options": "module_options_enabled",
        "forex": "module_forex_enabled",
        "crypto": "module_crypto_enabled",
    }

    def set_module_entitlement(self, tenant_id: str, module: str, enabled: bool) -> bool:
        """
        Grants or revokes one asset-class module for a tenant (super
        admin only -- see api/routers/admin_tenants.py). module must be
        one of "stocks", "options", "forex", "crypto". Returns False
        (not an exception) for an unrecognized module name or if
        tenant_id doesn't exist, both of which the router turns into a
        4xx rather than a 500.
        """
        _safe_rollback(self.db)

        column = self.MODULE_COLUMNS.get(module)
        if column is None:
            return False

        try:
            result = self.db.execute(text(f"""
                UPDATE tenants
                SET {column} = :enabled
                WHERE id = :id
            """), {"id": tenant_id, "enabled": enabled})

            self.db.commit()
            return result.rowcount > 0

        except Exception:
            logger.exception(
                "Failed to set module entitlement | tenant_id=%s module=%s", tenant_id, module
            )
            _safe_rollback(self.db)
            return False

    def get_module_entitlements(self, tenant_id: str) -> dict | None:
        """Returns {"stocks": bool, "options": bool, "forex": bool, "crypto": bool}, or None if tenant_id doesn't exist."""
        _safe_rollback(self.db)

        try:
            row = self.db.execute(text("""
                SELECT module_stocks_enabled, module_options_enabled,
                       module_forex_enabled, module_crypto_enabled
                FROM tenants
                WHERE id = :id
            """), {"id": tenant_id}).fetchone()

            if row is None:
                return None

            return {
                "stocks": bool(row[0]),
                "options": bool(row[1]),
                "forex": bool(row[2]),
                "crypto": bool(row[3]),
            }

        except Exception:
            logger.exception(
                "Failed to read module entitlements | tenant_id=%s", tenant_id
            )
            _safe_rollback(self.db)
            return None