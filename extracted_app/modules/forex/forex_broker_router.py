"""
modules/forex/forex_broker_router.py

Routes Forex orders to paper/live broker adapters.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from modules.forex.forex_broker_base import ForexBrokerOrderRequest
from modules.forex.forex_broker_registry import get_forex_broker_registry


class ForexBrokerRouter:
    def __init__(self, db=None, default_broker: str = "paper", configs: Optional[Dict[str, Dict[str, Any]]] = None):
        self.db = db
        self.default_broker = default_broker
        self.configs = configs or {}

    def route_order(self, *, broker: Optional[str] = None, **kwargs):
        broker_name = str(broker or kwargs.pop("broker", None) or self.default_broker or "paper").lower()
        adapter = get_forex_broker_registry().create(
            broker_name,
            db=self.db,
            config=self.configs.get(broker_name, {}),
        )
        req = ForexBrokerOrderRequest(
            pair=kwargs.get("pair") or kwargs.get("symbol"),
            side=kwargs.get("side"),
            units=float(kwargs.get("units") or kwargs.get("qty") or (float(kwargs.get("lots") or 1.0) * 100000)),
            order_type=kwargs.get("order_type", "MARKET"),
            limit_price=kwargs.get("limit_price"),
            stop_price=kwargs.get("stop_price"),
            take_profit=kwargs.get("take_profit") or kwargs.get("target_price"),
            account_id=kwargs.get("account_id"),
            portfolio_id=kwargs.get("portfolio_id"),
            client_order_id=kwargs.get("client_order_id"),
            metadata=kwargs,
        )
        result = adapter.submit_order(req)
        return result.to_dict() if hasattr(result, "to_dict") else result

    def cancel_order(self, broker_order_id: str, broker: str = "paper"):
        adapter = get_forex_broker_registry().create(
            broker,
            db=self.db,
            config=self.configs.get(broker, {}),
        )
        return adapter.cancel_order(broker_order_id)

    def health(self):
        return get_forex_broker_registry().health(db=self.db, configs=self.configs)


_ROUTER = None


def get_forex_broker_router(db=None, default_broker: str = "paper", configs: Optional[Dict[str, Dict[str, Any]]] = None):
    global _ROUTER
    if _ROUTER is None or (db is not None and _ROUTER.db is None):
        _ROUTER = ForexBrokerRouter(db=db, default_broker=default_broker, configs=configs)
    return _ROUTER
