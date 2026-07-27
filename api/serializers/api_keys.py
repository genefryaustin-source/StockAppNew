"""
api/serializers/api_keys.py

API key serialization -- shared by the tenant self-service router
(api/routers/api_keys.py) and the super-admin router
(api/routers/admin_api_keys.py). Never includes the raw key or its
hash; only display metadata.
"""

from __future__ import annotations

import json


def serialize_api_key(record, *, include_tenant: bool = False) -> dict:

    try:
        permissions = json.loads(record.permissions or "[]")
    except (TypeError, ValueError):
        permissions = []

    data = {
        "id": record.id,
        "name": record.name,
        "key_prefix": record.key_prefix,
        "key_suffix": record.key_suffix,
        "display": f"{record.key_prefix}_...{record.key_suffix}",
        "permissions": permissions,
        "rate_limit_per_minute": record.rate_limit_per_minute,
        "is_active": record.is_active,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "last_used_at": record.last_used_at.isoformat() if record.last_used_at else None,
        "expires_at": record.expires_at.isoformat() if record.expires_at else None,
        "revoked_at": record.revoked_at.isoformat() if record.revoked_at else None,
    }

    if include_tenant:
        data["tenant_id"] = record.tenant_id

    return data


def serialize_api_keys(records, *, include_tenant: bool = False) -> list[dict]:
    return [serialize_api_key(r, include_tenant=include_tenant) for r in records]