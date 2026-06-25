"""
modules/forex/forex_platform_controller.py
"""

from __future__ import annotations

from datetime import datetime, timezone

from modules.forex.forex_module_loader import get_forex_module_loader
from modules.forex.forex_registry import get_forex_registry
from modules.forex.forex_runtime_manager import get_forex_runtime_manager


class ForexPlatformController:
    """
    Top-level controller for the Forex platform.
    Intended as the single object app.py can interact with.
    """

    def __init__(self):
        self.loader = get_forex_module_loader()
        self.registry = get_forex_registry()
        self.runtime = get_forex_runtime_manager()

    def startup(self):
        self.registry.bootstrap()
        return self.runtime.start()

    def shutdown(self):
        return self.runtime.stop()

    def refresh(self):
        return self.runtime.refresh_quotes(force_refresh=True)

    def diagnostics(self):
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "runtime": self.runtime.status(),
            "registry": self.registry.summary(),
        }

    def render(self):
        self.loader.render()


_CONTROLLER=None

def get_forex_platform_controller():
    global _CONTROLLER
    if _CONTROLLER is None:
        _CONTROLLER = ForexPlatformController()
    return _CONTROLLER

def launch_forex():
    get_forex_platform_controller().render()
