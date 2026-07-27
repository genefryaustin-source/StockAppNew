"""
modules/forex/forex_runtime_manager.py
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, Any

from modules.forex.forex_registry import get_forex_registry
from modules.forex.forex_refresh_engine import get_forex_refresh_engine
from modules.forex.forex_bulk_refresh_engine import get_forex_bulk_refresh_engine
from modules.forex.forex_provider_health import get_forex_provider_health
from modules.forex.forex_provider_telemetry import get_forex_provider_telemetry
from modules.forex.forex_command_center_engine import get_forex_command_center_engine
from modules.forex.forex_runtime_context import build_forex_runtime_context

LOGGER=logging.getLogger("forex.runtime")

class ForexRuntimeManager:

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

        self.registry = get_forex_registry(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
        )

        self.refresh_engine = get_forex_refresh_engine()

        self.bulk_refresh = get_forex_bulk_refresh_engine()

        self.health = get_forex_provider_health()

        self.telemetry = get_forex_provider_telemetry()

        self.command_center = get_forex_command_center_engine()

        self.started = False

    def start(self)->Dict[str,Any]:
        self.registry.bootstrap()
        self.started=True
        return self.status()

    def stop(self)->Dict[str,Any]:
        self.started=False
        return {"status":"stopped"}

    def refresh_quotes(self, force_refresh:bool=True):
        if hasattr(self.refresh_engine,"refresh"):
            return self.refresh_engine.refresh(force_refresh=force_refresh)
        if hasattr(self.refresh_engine,"run"):
            return self.refresh_engine.run(force_refresh=force_refresh)
        return {"status":"unsupported"}

    def bulk_refresh_quotes(self):
        if hasattr(self.bulk_refresh,"run"):
            return self.bulk_refresh.run()
        if hasattr(self.bulk_refresh,"refresh_all"):
            return self.bulk_refresh.refresh_all()
        return {"status":"unsupported"}

    def collect_health(self):
        if hasattr(self.health,"summary"):
            return self.health.summary()
        if hasattr(self.health,"health_check"):
            return self.health.health_check()
        return {}

    def collect_telemetry(self):
        if hasattr(self.telemetry,"snapshot"):
            return self.telemetry.snapshot()
        if hasattr(self.telemetry,"collect"):
            return self.telemetry.collect()
        return {}

    def refresh_command_center(
            self,
            force_refresh: bool = False,
    ):
        runtime = build_forex_runtime_context(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,
            force_refresh=force_refresh,
            db=self.db,
        )
        print("=" * 80)
        print("FOREX RUNTIME IDENTITY")
        print("Tenant   :", runtime.tenant_id)
        print("User     :", runtime.user_id)
        print("Portfolio:", runtime.portfolio_id)
        print("Runtime  :", runtime.metadata.get("runtime_id"))
        print("=" * 80)
        return self.command_center.build(
            runtime=runtime,
            force_refresh=force_refresh,
        )

    def status(self):
        return {
            "runtime":"running" if self.started else "stopped",
            "timestamp":datetime.now(timezone.utc).isoformat(),
            "registry":self.registry.summary(),
            "provider_health":self.collect_health(),
        }

_RUNTIME = None

def get_forex_runtime_manager(
    db=None,
    tenant_id=None,
    user_id=None,
    portfolio_id=None,
):
    global _RUNTIME

    if (
        _RUNTIME is None
        or getattr(_RUNTIME, "db", None) is not db
        or getattr(_RUNTIME, "tenant_id", None) != tenant_id
        or getattr(_RUNTIME, "user_id", None) != user_id
        or getattr(_RUNTIME, "portfolio_id", None) != portfolio_id
    ):
        _RUNTIME = ForexRuntimeManager(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
        )

    return _RUNTIME

