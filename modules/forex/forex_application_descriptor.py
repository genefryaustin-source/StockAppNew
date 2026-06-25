"""
modules/forex/forex_application_descriptor.py

Application descriptor for the Forex subsystem.
"""
from __future__ import annotations
from copy import deepcopy

from modules.forex.forex_plugin import get_forex_plugin

_DESCRIPTOR={
    "application":"Forex",
    "module":"Forex",
    "display_name":"Foreign Exchange",
    "version":"1.0.0",
    "build":"2026.1",
    "compatibility":"StockApp 2026.x",
    "enterprise":True,
    "plugin":"ForexPlugin",
    "loader":"ForexModuleLoader",
    "bootstrap":"ForexPlatformBootstrap",
    "registry":"ForexPlatformRegistry",
    "status":"READY",
    "navigation":["Forex","Trading Desk","Institutional","Administration"],
    "health_checks":6,
    "services":18,
    "engines":14,
    "dashboards":20,
    "exports":{
        "platform_service":"ForexPlatformService",
        "enterprise_platform":"ForexEnterprisePlatform",
        "platform_gateway":"ForexPlatformGateway",
        "plugin":"ForexPlugin"
    }
}

_PLUGIN=None

def get_forex_application_descriptor():
    return deepcopy(_DESCRIPTOR)

def initialize_application(db=None):
    global _PLUGIN
    _PLUGIN=get_forex_plugin(db=db)
    return _PLUGIN.initialize(db=db)

def shutdown_application():
    if _PLUGIN is None:
        return {"status":"NOT_INITIALIZED"}
    return _PLUGIN.shutdown()

def application_health():
    if _PLUGIN is None:
        return {"status":"NOT_INITIALIZED"}
    return _PLUGIN.health()

def application_metadata():
    if _PLUGIN is None:
        return deepcopy(_DESCRIPTOR)
    meta=deepcopy(_DESCRIPTOR)
    meta["plugin_metadata"]=_PLUGIN.metadata()
    return meta
