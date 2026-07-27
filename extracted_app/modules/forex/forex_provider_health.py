
"""
modules/forex/forex_provider_health.py
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from modules.forex.providers.forex_provider_router import (
    get_forex_provider_router,
)


class ForexProviderHealth:

    def __init__(self):
        self.router=get_forex_provider_router()

    def summary(self)->dict[str,Any]:
        providers=self.router.get_status_rows()
        healthy=sum(1 for p in providers if p["health_score"]>=80)
        degraded=sum(1 for p in providers if 50<=p["health_score"]<80)
        unhealthy=sum(1 for p in providers if p["health_score"]<50)

        return {
            "timestamp":datetime.now(timezone.utc).isoformat(),
            "provider_count":len(providers),
            "healthy":healthy,
            "degraded":degraded,
            "unhealthy":unhealthy,
            "providers":providers,
        }

    def provider(self,name:str)->dict|None:
        p=self.router.get_provider(name)
        return None if p is None else p.as_row()

    def reset_provider(self,name:str)->None:
        self.router.reset_health(name)

    def reset_all(self)->None:
        for row in self.router.get_status_rows():
            self.router.reset_health(row["provider"])


_HEALTH=None

def get_forex_provider_health()->ForexProviderHealth:
    global _HEALTH
    if _HEALTH is None:
        _HEALTH=ForexProviderHealth()
    return _HEALTH
