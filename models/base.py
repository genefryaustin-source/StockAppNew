from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List
from sqlalchemy.orm import declarative_base

Base = declarative_base()

@dataclass
class BrokerOrderRequest:
    symbol: str
    side: str
    qty: float
    order_type: str = "market"
    tif: str = "day"
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None


@dataclass
class BrokerOrderResponse:
    broker_order_id: str
    status: str
    symbol: str
    side: str
    qty: float
    filled_qty: float = 0.0
    avg_fill_price: Optional[float] = None


@dataclass
class BrokerPosition:
    symbol: str
    qty: float
    avg_cost: float
    market_price: float
    market_value: float
    unrealized_pnl: float


class BrokerBase:
    name = "base"

    def submit_order(self, req: BrokerOrderRequest) -> BrokerOrderResponse:
        raise NotImplementedError

    def get_order(self, broker_order_id: str) -> BrokerOrderResponse:
        raise NotImplementedError

    def cancel_order(self, broker_order_id: str) -> bool:
        raise NotImplementedError

    def list_positions(self) -> List[BrokerPosition]:
        raise NotImplementedError

    def get_buying_power(self) -> float:
        raise NotImplementedError