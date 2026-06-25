"""
modules/forex/forex_module_loader.py
"""

from __future__ import annotations

from modules.forex.forex_master_workspace import render_forex_master_workspace
from modules.forex.forex_system_manager import initialize_forex_system

class ForexModuleLoader:
    """Application entry point for the Forex module."""

    def __init__(self):
        self.initialized=False

    def initialize(self):
        if not self.initialized:
            initialize_forex_system()
            self.initialized=True

    def render(self):
        self.initialize()
        render_forex_master_workspace()

_LOADER=None

def get_forex_module_loader():
    global _LOADER
    if _LOADER is None:
        _LOADER=ForexModuleLoader()
    return _LOADER

def load_forex_module():
    get_forex_module_loader().render()
