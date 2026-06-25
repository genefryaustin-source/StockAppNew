"""
modules/forex/forex_enterprise_distribution.py

Enterprise distribution facade for the complete Forex platform.
"""
from __future__ import annotations
from datetime import datetime, timezone

from modules.forex.forex_master_package import get_forex_master_package
from modules.forex.forex_distribution import get_forex_distribution

class ForexEnterpriseDistribution:
    VERSION="1.0.0"

    def __init__(self, db=None):
        self.db=db
        self.master=get_forex_master_package(db=db)
        self.dist=get_forex_distribution(db=db)

    def build(self):
        return self.master.build()

    def verify(self):
        return self.master.verify()

    def release(self, tag=None):
        return self.master.create_release(tag=tag)

    def export(self, output_dir):
        return self.dist.export_distribution(output_dir)

    def install(self):
        return self.master.install()

    def status(self):
        return {
            "package":"Forex Enterprise Distribution",
            "version":self.VERSION,
            "generated_at":datetime.now(timezone.utc).isoformat(),
            "distribution":self.dist.distribution_status(),
            "master":self.master.status(),
        }

_INSTANCE=None

def get_forex_enterprise_distribution(db=None):
    global _INSTANCE
    if _INSTANCE is None or (db is not None and _INSTANCE.db is None):
        _INSTANCE=ForexEnterpriseDistribution(db=db)
    return _INSTANCE
