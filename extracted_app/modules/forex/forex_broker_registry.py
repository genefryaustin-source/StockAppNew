"""
modules/forex/forex_broker_registry.py

Broker registry for paper and live broker adapters.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Type

from modules.forex.forex_broker_base import ForexBrokerBase
from modules.forex.forex_paper_broker import ForexPaperBroker
from modules.forex.forex_mt5_broker import ForexMT5Broker
from modules.forex.forex_oanda_broker import ForexOandaBroker
from modules.forex.forex_ibkr_broker import ForexIBKRBroker
from modules.forex.forex_dxtrade_broker import ForexDXTradeBroker


class ForexBrokerRegistry:
    def __init__(self):
        self._classes: Dict[str, Type[ForexBrokerBase]] = {
            "paper": ForexPaperBroker,
            "mt5": ForexMT5Broker,
            "oanda": ForexOandaBroker,
            "ibkr": ForexIBKRBroker,
            "dxtrade": ForexDXTradeBroker,
        }

    def names(self):
        return list(self._classes.keys())

    def get_class(self, name: str):
        return self._classes.get(str(name or "paper").lower())

    def create(self, name: str = "paper", db=None, config: Optional[Dict[str, Any]] = None):
        cls = self.get_class(name)
        if cls is None:
            raise ValueError(f"Unknown Forex broker: {name}")
        return cls(db=db, config=config or {})

    def health(self, db=None, configs: Optional[Dict[str, Dict[str, Any]]] = None):
        configs = configs or {}
        rows = []
        for name in self.names():
            broker = self.create(name, db=db, config=configs.get(name, {}))
            rows.append(broker.health())
        return rows


_REGISTRY = None


def get_forex_broker_registry():
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = ForexBrokerRegistry()
    return _REGISTRY
