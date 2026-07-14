"""
modules/risk_providers/provider_settings.py

Per-tenant enable/disable + config for external risk-analytics vendors.
Mirrors modules.portfolio.brokers.broker_settings -- same shape, same
"no row means not enabled" convention, backed by
modules.db.models.TenantRiskProviderSetting.
"""

from __future__ import annotations

import json
from datetime import datetime, UTC
from typing import Optional

from modules.db.models import TenantRiskProviderSetting


def _all_providers() -> list[str]:
    from modules.risk_providers.registry import available_risk_providers
    return available_risk_providers()


def list_provider_settings(db, tenant_id: str) -> dict:
    """Returns {provider_name: {"enabled": bool, "config": dict}} for every
    registered provider, defaulting missing rows to disabled/no config."""
    rows = {
        row.provider_name: row
        for row in db.query(TenantRiskProviderSetting)
        .filter(TenantRiskProviderSetting.tenant_id == tenant_id)
        .all()
    }
    out = {}
    for name in _all_providers():
        row = rows.get(name)
        config = {}
        if row and row.config_json:
            try:
                config = json.loads(row.config_json)
            except Exception:
                config = {}
        out[name] = {"enabled": bool(row.enabled) if row else False, "config": config}
    return out


def enabled_providers_for_tenant(db, tenant_id: Optional[str]) -> list[str]:
    """Returns provider names this tenant has enabled -- empty list if no
    tenant context, same safe-default philosophy as broker_settings."""
    if not tenant_id:
        return []
    settings = list_provider_settings(db, tenant_id)
    return [name for name, s in settings.items() if s["enabled"]]


def set_provider_enabled(db, tenant_id: str, provider_name: str, enabled: bool, user_id: str = None) -> None:
    row = (
        db.query(TenantRiskProviderSetting)
        .filter(TenantRiskProviderSetting.tenant_id == tenant_id,
                TenantRiskProviderSetting.provider_name == provider_name)
        .first()
    )
    if row:
        row.enabled = enabled
        row.updated_by_user_id = user_id
        row.updated_at = datetime.now(UTC)
    else:
        db.add(TenantRiskProviderSetting(
            tenant_id=tenant_id, provider_name=provider_name, enabled=enabled,
            updated_by_user_id=user_id,
        ))
    db.commit()


def set_provider_config(db, tenant_id: str, provider_name: str, config: dict, user_id: str = None) -> None:
    row = (
        db.query(TenantRiskProviderSetting)
        .filter(TenantRiskProviderSetting.tenant_id == tenant_id,
                TenantRiskProviderSetting.provider_name == provider_name)
        .first()
    )
    config_json = json.dumps(config)
    if row:
        row.config_json = config_json
        row.updated_by_user_id = user_id
        row.updated_at = datetime.now(UTC)
    else:
        db.add(TenantRiskProviderSetting(
            tenant_id=tenant_id, provider_name=provider_name, enabled=False,
            config_json=config_json, updated_by_user_id=user_id,
        ))
    db.commit()
