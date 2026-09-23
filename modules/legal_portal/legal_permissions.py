from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


PUBLIC_DOCUMENTS = {
    "privacy-policy",
    "terms-of-service",
    "cookie-policy",
    "financial-disclaimer",
    "risk-disclosure",
    "ai-disclosure",
    "market-data-disclaimer",
    "acceptable-use-policy",
    "api-license",
    "security",
    "accessibility",
    "contact",
}

INTERNAL_DOCUMENTS = {
    "compliance",
    "copyright",
    "dmca",
    "third-party-licenses",
}


@dataclass(frozen=True)
class LegalPrincipal:
    user_id: str | None
    tenant_id: str | None
    roles: frozenset[str]
    authenticated: bool
    is_super_admin: bool
    is_tenant_admin: bool


def _normalize_roles(values: Iterable[Any]) -> frozenset[str]:
    return frozenset(
        str(value).strip().lower()
        for value in values
        if str(value).strip()
    )


def principal_from_user(user: Any | None) -> LegalPrincipal:
    if user is None:
        return LegalPrincipal(
            user_id=None,
            tenant_id=None,
            roles=frozenset(),
            authenticated=False,
            is_super_admin=False,
            is_tenant_admin=False,
        )

    if isinstance(user, dict):
        roles_value = user.get("roles") or user.get("role") or []
        if isinstance(roles_value, str):
            roles_value = [roles_value]

        roles = _normalize_roles(roles_value)
        user_id = user.get("id") or user.get("user_id") or user.get("email")
        tenant_id = user.get("tenant_id")
        super_admin = bool(
            user.get("is_super_admin")
            or "super_admin" in roles
            or "superadmin" in roles
        )
        tenant_admin = bool(
            user.get("is_tenant_admin")
            or "tenant_admin" in roles
            or "admin" in roles
            or super_admin
        )
    else:
        roles_value = getattr(user, "roles", None) or getattr(user, "role", [])
        if isinstance(roles_value, str):
            roles_value = [roles_value]

        roles = _normalize_roles(roles_value)
        user_id = (
            getattr(user, "id", None)
            or getattr(user, "user_id", None)
            or getattr(user, "email", None)
        )
        tenant_id = getattr(user, "tenant_id", None)
        super_admin = bool(
            getattr(user, "is_super_admin", False)
            or "super_admin" in roles
            or "superadmin" in roles
        )
        tenant_admin = bool(
            getattr(user, "is_tenant_admin", False)
            or "tenant_admin" in roles
            or "admin" in roles
            or super_admin
        )

    return LegalPrincipal(
        user_id=str(user_id) if user_id is not None else None,
        tenant_id=str(tenant_id) if tenant_id is not None else None,
        roles=roles,
        authenticated=True,
        is_super_admin=super_admin,
        is_tenant_admin=tenant_admin,
    )


def can_view_document(principal: LegalPrincipal, document_key: str) -> bool:
    if document_key in PUBLIC_DOCUMENTS:
        return True

    if document_key in INTERNAL_DOCUMENTS:
        return principal.authenticated and (
            principal.is_tenant_admin or principal.is_super_admin
        )

    return principal.is_super_admin


def can_manage_legal_portal(principal: LegalPrincipal) -> bool:
    return principal.is_super_admin


def can_view_health(principal: LegalPrincipal) -> bool:
    return principal.is_tenant_admin or principal.is_super_admin
