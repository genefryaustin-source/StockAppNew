"""
modules/forex/forex_release_package.py

Release packaging and version management for the Forex subsystem.
"""
from __future__ import annotations
from datetime import datetime, timezone

from modules.forex.forex_package_manager import get_forex_package_manager


class ForexReleasePackage:
    VERSION="1.0.0"

    def __init__(self, db=None):
        self.db=db
        self.pm=get_forex_package_manager(db=db)

    def create_release(self, tag=None):
        return {
            "status":"RELEASE_CREATED",
            "version":self.VERSION,
            "tag":tag or f"v{self.VERSION}",
            "created_at":datetime.now(timezone.utc).isoformat(),
            "distribution":self.pm.build(),
        }

    def verify_release(self):
        return self.pm.verify()

    def publish_manifest(self):
        return {
            "package":"Forex",
            "version":self.VERSION,
            "published":True,
            "timestamp":datetime.now(timezone.utc).isoformat(),
        }

    def release_status(self):
        return {
            "release":self.VERSION,
            "package_status":self.pm.status(),
        }

_RELEASE=None

def get_forex_release_package(db=None):
    global _RELEASE
    if _RELEASE is None or (db is not None and _RELEASE.db is None):
        _RELEASE=ForexReleasePackage(db=db)
    return _RELEASE
