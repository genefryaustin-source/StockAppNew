"""
modules/portfolio/brokers/broker_settings.py

Per-tenant enable/disable switches for broker/execution providers
(Alpaca, Tradier, IBKR, ...). Most tenants only use one real broker, so
rather than showing every connected provider in the Trading & Execution
broker dropdown, a tenant admin (or super admin) turns on the ones their
tenant should see; everyone else only sees "Paper" until one is enabled.

Backed by modules.db.models.TenantBrokerSetting. No row for a given
(tenant_id, broker_name) means "not explicitly enabled" -- "paper" is
always available regardless of settings, since it has no credentials and
can't cause a real trade.
"""

from __future__ import annotations

from datetime import datetime, UTC
from typing import Optional

from modules.db.models import TenantBrokerSetting

ALWAYS_ENABLED = {"paper"}


def _real_brokers() -> list[str]:
    """All broker names the app knows about, excluding "paper" (which
    needs no enable/disable toggle)."""
    from modules.portfolio.brokers.factory import available_brokers
    return [b for b in available_brokers() if b not in ALWAYS_ENABLED]


def list_broker_settings(db, tenant_id: str) -> dict:
    """Returns {broker_name: enabled_bool} for every real broker the app
    supports, defaulting missing rows to False (opt-in, not opt-out)."""
    rows = {
        row.broker_name: row.enabled
        for row in db.query(TenantBrokerSetting)
        .filter(TenantBrokerSetting.tenant_id == tenant_id)
        .all()
    }
    return {name: rows.get(name, False) for name in _real_brokers()}


def enabled_brokers_for_tenant(db, tenant_id: Optional[str]) -> list[str]:
    """Returns the list of broker names this tenant is allowed to pick in
    the Trading & Execution broker dropdown -- always includes "paper".
    If tenant_id is None (no tenant context, e.g. a background job), only
    "paper" is returned as the safe default."""
    if not tenant_id:
        return ["paper"]
    settings = list_broker_settings(db, tenant_id)
    return ["paper"] + [name for name, enabled in settings.items() if enabled]


def set_broker_enabled(db, tenant_id: str, broker_name: str, enabled: bool, user_id: str = None) -> None:
    if broker_name in ALWAYS_ENABLED:
        return  # paper is always on; nothing to persist

    row = (
        db.query(TenantBrokerSetting)
        .filter(TenantBrokerSetting.tenant_id == tenant_id, TenantBrokerSetting.broker_name == broker_name)
        .first()
    )
    if row:
        row.enabled = enabled
        row.updated_by_user_id = user_id
        row.updated_at = datetime.now(UTC)
    else:
        db.add(TenantBrokerSetting(
            tenant_id=tenant_id,
            broker_name=broker_name,
            enabled=enabled,
            updated_by_user_id=user_id,
        ))
    db.commit()
