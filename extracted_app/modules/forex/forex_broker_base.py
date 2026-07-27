"""
modules/forex/forex_broker_base.py

Phase 11 — Broker abstraction base layer.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class ForexBrokerOrderRequest:
    pair: str
    side: str
    units: float
    order_type: str = "MARKET"
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    take_profit: Optional[float] = None
    account_id: Optional[str] = None
    portfolio_id: Optional[str] = None
    client_order_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ForexBrokerOrderResult:
    status: str
    broker: str
    broker_order_id: Optional[str]
    message: str
    pair: Optional[str] = None
    side: Optional[str] = None
    units: Optional[float] = None
    avg_fill_price: Optional[float] = None
    filled_qty: Optional[float] = None
    submitted_at: Optional[str] = None
    filled_at: Optional[str] = None
    raw: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ForexBrokerBase(ABC):
    name = "base"
    supports_live = False

    def __init__(self, db=None, config: Optional[Dict[str, Any]] = None):
        self.db = db
        self.config = config or {}

    @abstractmethod
    def health(self) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def submit_order(self, request: ForexBrokerOrderRequest) -> ForexBrokerOrderResult:
        raise NotImplementedError

    @abstractmethod
    def cancel_order(self, broker_order_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    def positions(self) -> List[Dict[str, Any]]:
        return []

    def orders(self) -> List[Dict[str, Any]]:
        return []

    def account(self) -> Dict[str, Any]:
        return {}

    def now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
