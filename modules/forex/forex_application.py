"""
modules/forex/forex_application.py
"""

from __future__ import annotations

from modules.forex.forex_platform_controller import (
    get_forex_platform_controller,
)


class ForexApplication:
    """
    High-level application facade for the Forex platform.
    """

    def __init__(self):
        self.controller = get_forex_platform_controller()

    def startup(self):
        return self.controller.startup()

    def shutdown(self):
        return self.controller.shutdown()

    def refresh(self):
        return self.controller.refresh()

    def diagnostics(self):
        return self.controller.diagnostics()

    def render(self):
        self.controller.render()


_APP = None


def get_forex_application():
    global _APP
    if _APP is None:
        _APP = ForexApplication()
    return _APP


def run_forex():
    get_forex_application().render()
