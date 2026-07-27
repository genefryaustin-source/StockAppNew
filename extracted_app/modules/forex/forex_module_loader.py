"""
modules/forex/forex_module_loader.py

Dynamic loader for the Forex subsystem.
"""
from __future__ import annotations
from datetime import datetime, timezone
import time

from modules.forex.forex_platform_bootstrap import (
    bootstrap_forex_platform,
    shutdown_forex_platform,
)
from modules.forex.forex_platform_registry import get_forex_platform_registry
from modules.forex.forex_platform_service import get_forex_platform_service
from modules.forex.forex_platform_gateway import get_forex_platform_gateway
from modules.forex.forex_enterprise_platform import get_forex_enterprise_platform

_SERVICE=None
_REGISTRY=None

def load_forex_module(db=None):
    global _SERVICE,_REGISTRY
    start=time.perf_counter()

    report=bootstrap_forex_platform(db=db)
    _SERVICE=get_forex_platform_service(db=db)
    gateway=get_forex_platform_gateway(db=db)
    platform=get_forex_enterprise_platform(db=db)
    _REGISTRY=get_forex_platform_registry(db=db)

    for name,obj in {
        "platform_service":_SERVICE,
        "platform_gateway":gateway,
        "enterprise_platform":platform,
        "bootstrap_report":report,
    }.items():
        _REGISTRY.register_component(name,obj)

    return {
        "status":"LOADED",
        "module":"Forex",
        "services_registered":18,
        "engines_registered":14,
        "dashboards_registered":20,
        "validation_suites_registered":6,
        "startup_time_ms":round((time.perf_counter()-start)*1000,2),
        "platform_ready":True,
        "bootstrap":report,
        "registry":_REGISTRY.health_summary(),
    }

def unload_forex_module():
    shutdown_forex_platform()
    return {"status":"UNLOADED","module":"Forex"}

def reload_forex_module(db=None):
    unload_forex_module()
    return load_forex_module(db=db)

def module_status():
    if _SERVICE is None:
        return {"status":"NOT_LOADED"}
    return {
        "status":"LOADED",
        "metadata":_SERVICE.metadata(),
        "registry":_REGISTRY.health_summary() if _REGISTRY else {},
        "health":_SERVICE.health(),
    }


# ==============================================================================
# OOP wrapper
# ==============================================================================
#
# forex_platform_controller.py expects a loader *object* (get_forex_module_loader()
# then self.loader.render()), but this module only ever exposed free functions.
# Thin wrapper so both styles work off the same load/unload/status functions.


class ForexModuleLoader:
    def __init__(self, db=None):
        self.db = db

    def load(self):
        return load_forex_module(db=self.db)

    def unload(self):
        return unload_forex_module()

    def reload(self):
        return reload_forex_module(db=self.db)

    def status(self):
        return module_status()

    def render(self):
        """
        forex_platform_controller.py calls this with no return value used;
        it's a status snapshot, not a Streamlit UI render. Ensures the
        module is loaded, then returns current status for callers that do
        use the return value.
        """
        if _SERVICE is None:
            self.load()
        return self.status()


_LOADER = None


def get_forex_module_loader(db=None) -> ForexModuleLoader:
    global _LOADER
    if _LOADER is None or (db is not None and _LOADER.db is None):
        _LOADER = ForexModuleLoader(db=db)
    return _LOADER
