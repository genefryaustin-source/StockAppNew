"""
modules/forex/forex_system_manager.py
"""

from __future__ import annotations

from datetime import datetime, timezone

from modules.forex.forex_runtime_manager import get_forex_runtime_manager
from modules.forex.forex_workspace import render_forex_workspace
from modules.forex.forex_registry import get_forex_registry


class ForexSystemManager:
    """Top-level coordinator for the Forex subsystem."""

    def __init__(
        self,
        db=None,
        tenant_id=None,
        user_id=None,
        portfolio_id=None,
    ):
        self.db = db
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.portfolio_id = portfolio_id

        self.runtime = get_forex_runtime_manager(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
        )

        self.registry = get_forex_registry(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
        )

    def initialize(self):
        self.registry.bootstrap()
        return self.runtime.start()

    def system_status(self):
        status = self.runtime.status()
        status["generated_at"] = datetime.now(timezone.utc).isoformat()
        return status

    def refresh(self):
        return {
            "quotes": self.runtime.refresh_quotes(),
            "bulk_refresh": self.runtime.bulk_refresh_quotes(),
            "command_center": self.runtime.refresh_command_center(),
            "telemetry": self.runtime.collect_telemetry(),
        }

    def render(self):
        render_forex_workspace(
            db=self.db,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,
        )


_MANAGER = None

def get_forex_system_manager(
    db=None,
    tenant_id=None,
    user_id=None,
    portfolio_id=None,
):
    global _MANAGER

    if (
        _MANAGER is None
        or _MANAGER.db is not db
        or _MANAGER.tenant_id != tenant_id
        or _MANAGER.user_id != user_id
        or _MANAGER.portfolio_id != portfolio_id
    ):

        _MANAGER = ForexSystemManager(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
        )

    return _MANAGER

def initialize_forex_system(
    db=None,
    tenant_id=None,
    user_id=None,
    portfolio_id=None,
):
    return get_forex_system_manager(
        db=db,
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
    ).initialize()

def render_forex_system(
    db=None,
    tenant_id=None,
    user_id=None,
    portfolio_id=None,
):
    return get_forex_system_manager(
        db=db,
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
    ).render()
