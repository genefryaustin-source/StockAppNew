from __future__ import annotations

from datetime import datetime, UTC
from typing import List
import uuid
from sqlalchemy import text
from modules.market_data.service import get_latest_price_map
from modules.portfolio.brokers.base import (
    BrokerBase, BrokerOrderRequest, BrokerOrderResponse, BrokerPosition
)
from modules.portfolio.accounting_service import AccountingService

class PaperBroker(BrokerBase):
    name = "paper"

    def __init__(self, position_store=None, cash: float = 100000.0):
        self.position_store = position_store
        self.cash = float(cash)
        self._orders = {}

        # ✅ NEW: track positions internally (non-breaking)
        self._positions = {}  # { symbol: { qty, avg_price } }

    def _normalize(self, symbol: str) -> str:
        return str(symbol).upper().strip()

    def _get_last_price(self, symbol: str) -> float:
        symbol = self._normalize(symbol)

        price_map = get_latest_price_map([symbol])
        price = price_map.get(symbol)

        if price is None:
            # fallback lookup (in case of key mismatch)
            for k, v in price_map.items():
                if str(k).upper() == symbol:
                    price = v
                    break

        print("🧪 PAPER BROKER PRICE:", symbol, price)

        if price is None:
            raise ValueError(f"Unable to get price for {symbol}")

        return float(price)

    def submit_order(self, req: BrokerOrderRequest) -> BrokerOrderResponse:
        symbol = self._normalize(req.symbol)
        side = str(req.side).lower()

        px = self._get_last_price(symbol)

        broker_order_id = f"paper-{uuid.uuid4().hex[:16]}"
        status = "filled" if req.order_type == "market" else "accepted"

        filled_qty = float(req.qty) if status == "filled" else 0.0
        avg_fill_price = float(px) if status == "filled" else None

        # ---------------------------------------------------
        # ✅ CORE FIX: UPDATE CASH + POSITIONS
        # ---------------------------------------------------
        if status == "filled" and filled_qty > 0:
            trade_value = filled_qty * avg_fill_price
            commission = max(1.0, filled_qty * 0.005)  # match order_service

            if side == "buy":
                total_cost = trade_value + commission

                if self.cash < total_cost:
                    raise ValueError("Insufficient buying power")

                self.cash -= total_cost

                pos = self._positions.get(symbol, {"qty": 0.0, "avg_price": 0.0})

                new_qty = pos["qty"] + filled_qty

                if new_qty > 0:
                    new_avg = (
                        (pos["qty"] * pos["avg_price"] + filled_qty * avg_fill_price)
                        / new_qty
                    )
                else:
                    new_avg = 0.0

                self._positions[symbol] = {
                    "qty": new_qty,
                    "avg_price": new_avg
                }

            elif side == "sell":
                pos = self._positions.get(symbol, {"qty": 0.0, "avg_price": 0.0})

                if pos["qty"] < filled_qty:
                    raise ValueError("Not enough shares to sell")

                total_proceeds = trade_value - commission

                self.cash += total_proceeds

                new_qty = pos["qty"] - filled_qty

                if new_qty <= 0:
                    self._positions.pop(symbol, None)
                else:
                    self._positions[symbol] = {
                        "qty": new_qty,
                        "avg_price": pos["avg_price"]
                    }

        # ---------------------------------------------------

        resp = BrokerOrderResponse(
            broker_order_id=broker_order_id,
            status=status,
            symbol=symbol,
            side=side,
            qty=float(req.qty),
            filled_qty=filled_qty,
            avg_fill_price=avg_fill_price,
        )

        self._orders[broker_order_id] = {
            "response": resp,
            "created_at": datetime.now(UTC),
        }

        print("💰 PAPER CASH AFTER TRADE:", self.cash)
        print("📊 PAPER POSITIONS:", self._positions)

        return resp

    def get_order(self, broker_order_id: str) -> BrokerOrderResponse:
        return self._orders[broker_order_id]["response"]

    def cancel_order(self, broker_order_id: str) -> bool:
        order = self._orders.get(broker_order_id)
        if not order:
            return False

        resp = order["response"]

        if resp.status in {"filled", "canceled"}:
            return False

        resp.status = "canceled"
        return True

    def list_positions(self) -> List[BrokerPosition]:
        positions = []

        for sym, data in self._positions.items():
            positions.append(
                BrokerPosition(
                    symbol=sym,
                    qty=float(data["qty"]),
                    avg_price=float(data["avg_price"]),
                )
            )

        return positions



    def get_buying_power(self, portfolio_id=None) -> float:
        try:
            if self.position_store is not None and portfolio_id is not None:

                result = self.position_store.execute(
                    text("""
                        SELECT COALESCE(SUM(amount), 0)
                        FROM portfolio_cash_ledger
                        WHERE portfolio_id = :pid
                    """),
                    {"pid": portfolio_id},
                ).fetchone()

                if result and result[0] is not None:
                    return float(result[0])

            else:
                # ---------------------------------
                # SAFE FALLBACK (NO NOISE)
                # ---------------------------------
                if self.position_store is None or portfolio_id is None:
                    # silently fallback — broker is no longer source of truth
                    return 0.0

        except Exception as e:
            print("❌ Broker cash read error:", e)

        return 0.0  # 🔥 DO NOT fallback to self.cash anymore