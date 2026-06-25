"""
modules/forex/forex_startup.py

Forex subsystem startup and diagnostics.
"""

from __future__ import annotations

import logging

from modules.forex.forex_registry import get_forex_registry

LOGGER=logging.getLogger("forex.startup")


class ForexStartup:

    def __init__(self):
        self.registry=get_forex_registry()

    def initialize(self):
        self.registry.bootstrap()
        return self.health_check()

    def health_check(self):
        report={
            "status":"healthy",
            "engines":{},
            "services":{},
            "providers":{},
            "errors":[]
        }

        for name,obj in self.registry.engines.items():
            report["engines"][name]=obj is not None

        for name,obj in self.registry.services.items():
            report["services"][name]=obj is not None

        for name,obj in self.registry.providers.items():
            ok=True
            try:
                if hasattr(obj,"health_check"):
                    result=obj.health_check()
                    ok=bool(result.get("healthy",True))
            except Exception as exc:
                ok=False
                report["errors"].append(f"{name}: {exc}")
            report["providers"][name]=ok

        if report["errors"]:
            report["status"]="degraded"

        LOGGER.info("Forex startup complete: %s",report["status"])
        return report


_STARTUP=None

def get_forex_startup():
    global _STARTUP
    if _STARTUP is None:
        _STARTUP=ForexStartup()
    return _STARTUP

def initialize_forex_subsystem():
    return get_forex_startup().initialize()
