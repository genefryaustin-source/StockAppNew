"""
modules/forex/forex_package_manager.py

Package manager for the Forex subsystem.
"""
from __future__ import annotations

from modules.forex.forex_distribution import get_forex_distribution
from modules.forex.forex_installer import get_forex_installer

class ForexPackageManager:
    VERSION="1.0.0"

    def __init__(self, db=None):
        self.db=db
        self.distribution=get_forex_distribution(db=db)
        self.installer=get_forex_installer(db=db)

    def build(self):
        return self.distribution.build_distribution()

    def verify(self):
        return self.distribution.verify_distribution()

    def install(self):
        return self.installer.install()

    def uninstall(self):
        return self.installer.uninstall()

    def repair(self):
        return self.installer.repair()

    def status(self):
        return self.distribution.distribution_status()

_PACKAGE_MANAGER=None

def get_forex_package_manager(db=None):
    global _PACKAGE_MANAGER
    if _PACKAGE_MANAGER is None or (db is not None and _PACKAGE_MANAGER.db is None):
        _PACKAGE_MANAGER=ForexPackageManager(db=db)
    return _PACKAGE_MANAGER
