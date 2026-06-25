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

    def __init__(self):
        self.runtime = get_forex_runtime_manager()
        self.registry = get_forex_registry()

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
        render_forex_workspace()


_MANAGER=None

def get_forex_system_manager():
    global _MANAGER
    if _MANAGER is None:
        _MANAGER=ForexSystemManager()
    return _MANAGER

def initialize_forex_system():
    return get_forex_system_manager().initialize()

def render_forex_system():
    return get_forex_system_manager().render()
