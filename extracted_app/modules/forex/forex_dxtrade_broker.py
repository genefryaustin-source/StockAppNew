"""
modules/forex/forex_dxtrade_broker.py

Phase 11 broker adapter placeholder.

This adapter is production-safe: it will not place live trades until credentials
and live execution are explicitly configured.
"""

from __future__ import annotations

from typing import Any, Dict

from modules.forex.forex_broker_base import ForexBrokerBase, ForexBrokerOrderRequest, ForexBrokerOrderResult


class ForexDXTradeBroker(ForexBrokerBase):
    name = "dxtrade"
    supports_live = True

    def health(self) -> Dict[str, Any]:
        enabled = bool(self.config.get("enabled") and self.config.get("live_enabled"))
        return {
            "broker": self.name,
            "status": "CONFIGURED" if enabled else "DISABLED",
            "live_enabled": enabled,
            "message": "Live adapter scaffold. Add credentials and API calls before enabling.",
        }

    def submit_order(self, request: ForexBrokerOrderRequest) -> ForexBrokerOrderResult:
        if not (self.config.get("enabled") and self.config.get("live_enabled")):
            return ForexBrokerOrderResult(
                status="REJECTED",
                broker=self.name,
                broker_order_id=None,
                message=f"{self.name} live trading is disabled.",
                pair=request.pair,
                side=request.side,
                units=request.units,
                raw={"request": request.to_dict(), "health": self.health()},
            )

        return ForexBrokerOrderResult(
            status="REJECTED",
            broker=self.name,
            broker_order_id=None,
            message=f"{self.name} adapter is configured but live API submit implementation is intentionally not enabled yet.",
            pair=request.pair,
            side=request.side,
            units=request.units,
            raw={"request": request.to_dict()},
        )

    def cancel_order(self, broker_order_id: str) -> Dict[str, Any]:
        return {
            "status": "REJECTED",
            "broker": self.name,
            "broker_order_id": broker_order_id,
            "message": f"{self.name} cancel implementation is not enabled yet.",
        }
