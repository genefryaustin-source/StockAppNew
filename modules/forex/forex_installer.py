"""
modules/forex/forex_installer.py

Installer for the Forex subsystem.
"""
from __future__ import annotations

from modules.forex.forex_distribution import get_forex_distribution
from modules.forex.forex_platform_bootstrap import bootstrap_forex_platform


class ForexInstaller:
    VERSION="1.0.0"

    def __init__(self, db=None):
        self.db=db
        self.dist=get_forex_distribution(db=db)

    def install(self):
        return {
            "distribution": self.dist.build_distribution(),
            "bootstrap": bootstrap_forex_platform(db=self.db),
            "status":"INSTALLED",
        }

    def verify(self):
        return self.dist.verify_distribution()

    def uninstall(self):
        return {
            "status":"UNINSTALLED",
            "module":"Forex"
        }

    def repair(self):
        return {
            "verify": self.verify(),
            "install": self.install(),
            "status":"REPAIRED"
        }

_INSTALLER=None

def get_forex_installer(db=None):
    global _INSTALLER
    if _INSTALLER is None or (db is not None and _INSTALLER.db is None):
        _INSTALLER=ForexInstaller(db=db)
    return _INSTALLER
