"""
modules/forex/forex_master_package.py

Master packaging facade for the Forex subsystem.
"""
from __future__ import annotations

from modules.forex.forex_release_package import get_forex_release_package
from modules.forex.forex_package_manager import get_forex_package_manager
from modules.forex.forex_installer import get_forex_installer


class ForexMasterPackage:
    VERSION="1.0.0"

    def __init__(self, db=None):
        self.db=db
        self.release=get_forex_release_package(db=db)
        self.packages=get_forex_package_manager(db=db)
        self.installer=get_forex_installer(db=db)

    def build(self):
        return self.packages.build()

    def verify(self):
        return self.packages.verify()

    def create_release(self, tag=None):
        return self.release.create_release(tag=tag)

    def publish(self):
        return self.release.publish_manifest()

    def install(self):
        return self.installer.install()

    def uninstall(self):
        return self.installer.uninstall()

    def repair(self):
        return self.installer.repair()

    def status(self):
        return {
            "version":self.VERSION,
            "distribution":self.packages.status(),
            "release":self.release.release_status(),
        }

_MASTER=None

def get_forex_master_package(db=None):
    global _MASTER
    if _MASTER is None or (db is not None and _MASTER.db is None):
        _MASTER=ForexMasterPackage(db=db)
    return _MASTER
