from __future__ import annotations

from datetime import datetime, UTC

import streamlit as st

from modules.market_data.service import get_latest_price_map
from models.trading import TradeOrder, TradeFill, PortfolioPosition
from modules.portfolio.brokers.base import BrokerOrderRequest
from modules.portfolio.pnl_engine import (
    estimate_transaction_cost,
    update_position_after_fill,
    mark_to_market,
    closing_trade_metrics,
)
from modules.portfolio.accounting_service import AccountingService
from modules.portfolio.closed_trade_service import ClosedTradeService


class SimulatedBrokerResponse:
    def __init__(self, req: BrokerOrderRequest, price: float):
        self.broker_order_id = f"SIM-{req.symbol}-{int(datetime.now(UTC).timestamp())}"
        self.symbol = str(req.symbol).upper()
        self.side = str(req.side).lower()
        self.qty = float(req.qty)
        self.status = "filled"
        self.filled_qty = float(req.qty)
        self.avg_fill_price = float(price)


class OrderService:
    def __init__(self, db_session, broker=None, market_data_service=None):
        self.db = db_session
        self.broker = broker
        self.market_data_service = market_data_service
        self.accounting = AccountingService(db_session)
        self.closed_trade_service = ClosedTradeService(db_session)

    def _normalize_symbol(self, symbol: str) -> str:
        return str(symbol).upper().strip()

    def _estimate_commission(
        self,
        symbol: str,
        qty: float,
        price: float,
        broker: str = "paper",
    ) -> float:
        if str(broker).lower() == "paper":
            return round(max(1.0, float(qty) * 0.005), 2)
        return 0.0

    def _get_reference_price(self, symbol: str) -> float:
        symbol = self._normalize_symbol(symbol)

        try:
            price_map = get_latest_price_map([symbol])

            price = price_map.get(symbol)
            if price is None:
                for k, v in price_map.items():
                    if str(k).upper() == symbol:
                        price = v
                        break

            print("🔍 PRICE LOOKUP:", symbol, price)
            print("🚀 USING NEW PRICE FUNCTION", symbol)

            if price is None:
                raise ValueError(f"No price found for {symbol}")

            return float(price)

        except Exception as e:
            print("❌ PRICE FETCH ERROR:", symbol, e)
            raise ValueError(f"Unable to get reference price for {symbol}")

    def _get_available_position_qty(self, portfolio_id, symbol) -> float:
        symbol = self._normalize_symbol(symbol)

        position = (
            self.db.query(PortfolioPosition)
            .filter(
                PortfolioPosition.portfolio_id == portfolio_id,
                PortfolioPosition.symbol == symbol,
            )
            .one_or_none()
        )

        return float(position.qty or 0.0) if position is not None else 0.0

    def submit_order(
        self,
        portfolio_id,
        user_id,
        symbol,
        side,
        qty,
        order_type="market",
        tif="day",
        limit_price=None,
        stop_price=None,
    ):
        try:
            self.accounting.ensure_seed_cash(portfolio_id)

            symbol = self._normalize_symbol(symbol)
            side = str(side).lower().strip()
            qty = float(qty)

            # ---------------------------------------
            # 🚨 SELL VALIDATION (CRITICAL FIX)
            # ---------------------------------------
            if side == "sell":
                available_qty = self._get_available_position_qty(portfolio_id, symbol)

                print("🚨 SELL VALIDATION:", {
                    "portfolio_id": portfolio_id,
                    "symbol": symbol,
                    "requested_qty": qty,
                    "available_qty": available_qty,
                })
                print("✅ PASSED SELL VALIDATION — CONTINUING EXECUTION")
                if available_qty < qty:
                    raise ValueError(
                        f"Not enough shares to sell: requested {qty}, available {available_qty}"

                    )
            print("✅ DID NOT PASSED SELL VALIDATION — CONTINUING EXECUTION")
            # ---------------------------------------
            # GET REFERENCE PRICE
            # ---------------------------------------
            ref_price = self._get_reference_price(symbol)

            # ---------------------------------------
            # BUILD ORDER REQUEST
            # ---------------------------------------
            req = BrokerOrderRequest(
                symbol=symbol,
                side=side,
                qty=qty,
                order_type=order_type,
                tif=tif,
                limit_price=limit_price,
                stop_price=stop_price,
            )

            # ---------------------------------------
            # FORCE PAPER EXECUTION (BYPASS BROKER VALIDATION)
            # ---------------------------------------
            broker_resp = SimulatedBrokerResponse(req, ref_price)
            broker_name = "paper"

            exec_price = float(broker_resp.avg_fill_price or ref_price or 0.0)

            order = TradeOrder(
                portfolio_id=portfolio_id,
                user_id=user_id,
                broker=broker_name,
                broker_order_id=broker_resp.broker_order_id,
                symbol=self._normalize_symbol(broker_resp.symbol),
                side=str(broker_resp.side).lower(),
                order_type=order_type,
                tif=tif,
                qty=float(broker_resp.qty),
                limit_price=limit_price,
                stop_price=stop_price,
                status=broker_resp.status,
                submitted_at=datetime.now(UTC),
                filled_at=datetime.now(UTC) if float(broker_resp.filled_qty or 0) > 0 else None,
                avg_fill_price=exec_price if float(broker_resp.filled_qty or 0) > 0 else None,
                filled_qty=float(broker_resp.filled_qty or 0.0),
                estimated_commission=self._estimate_commission(
                    symbol=self._normalize_symbol(broker_resp.symbol),
                    qty=float(broker_resp.qty),
                    price=exec_price,
                    broker=broker_name,
                ),
                estimated_slippage=0.0,
                actual_commission=0.0,
                actual_slippage=0.0,
                notes=None,
                updated_at=datetime.now(UTC),
            )

            self.db.add(order)
            self.db.flush()

            if float(broker_resp.filled_qty or 0) > 0 and broker_resp.avg_fill_price is not None:

                trading_cfg = st.secrets.get("trading", {})

                cost = estimate_transaction_cost(
                    qty=float(broker_resp.filled_qty),
                    reference_price=float(ref_price),
                    fill_price=float(broker_resp.avg_fill_price),
                    commission_per_order=float(trading_cfg.get("COMMISSION_PER_ORDER", 0.0)),
                    min_commission=float(trading_cfg.get("MIN_COMMISSION", 0.0)),
                )

                fill = TradeFill(
                    order_id=order.id,
                    symbol=self._normalize_symbol(broker_resp.symbol),
                    side=str(broker_resp.side).lower(),
                    qty=float(broker_resp.filled_qty),
                    price=float(broker_resp.avg_fill_price),
                    commission=float(cost.commission),
                    slippage=float(cost.slippage),
                )
                self.db.add(fill)

                order.estimated_commission = float(cost.commission)
                order.estimated_slippage = float(cost.slippage)
                order.actual_commission = float(cost.commission)
                order.actual_slippage = float(cost.slippage)
                order.updated_at = datetime.now(UTC)

                # ---------------------------------------
                # POSITION LOAD / INIT
                # ---------------------------------------
                symbol_norm = self._normalize_symbol(broker_resp.symbol)

                position = (
                    self.db.query(PortfolioPosition)
                    .filter(
                        PortfolioPosition.portfolio_id == portfolio_id,
                        PortfolioPosition.symbol == symbol_norm,
                    )
                    .one_or_none()
                )

                if position is None:
                    position = PortfolioPosition(
                        portfolio_id=portfolio_id,
                        symbol=symbol_norm,
                        qty=0.0,
                        avg_cost=0.0,
                        realized_pnl=0.0,
                    )
                    self.db.add(position)
                    self.db.flush()

                prior_qty = float(position.qty or 0.0)
                prior_avg_cost = float(position.avg_cost or 0.0)
                prior_updated_at = getattr(position, "updated_at", None)

                fill_qty = float(broker_resp.filled_qty)
                fill_price = float(broker_resp.avg_fill_price)
                side_norm = str(broker_resp.side).lower().strip()

                # ---------------------------------------
                # POSITION + PNL CALC (SAFE LOGIC)
                # ---------------------------------------
                realized_pnl = 0.0

                if side_norm == "buy":
                    new_qty = prior_qty + fill_qty
                    total_cost_basis = (prior_qty * prior_avg_cost) + (fill_qty * fill_price)
                    new_avg_cost = total_cost_basis / new_qty if new_qty != 0 else 0.0

                elif side_norm == "sell":
                    closed_qty = min(fill_qty, prior_qty)
                    realized_pnl = (fill_price - prior_avg_cost) * closed_qty

                    new_qty = prior_qty - fill_qty
                    new_avg_cost = prior_avg_cost if new_qty != 0 else 0.0

                else:
                    new_qty = prior_qty
                    new_avg_cost = prior_avg_cost

                # ---------------------------------------
                # APPLY POSITION UPDATE
                # ---------------------------------------
                if abs(new_qty) < 1e-9:
                    position.qty = 0.0
                    position.avg_cost = 0.0
                    position.market_value = 0.0
                    position.unrealized_pnl = 0.0
                else:
                    position.qty = float(new_qty)
                    position.avg_cost = float(new_avg_cost)
                    position.market_value = float(new_qty) * fill_price
                    position.unrealized_pnl = float(
                        mark_to_market(
                            float(new_qty),
                            float(new_avg_cost),
                            fill_price,
                        )
                    )

                position.realized_pnl = (
                        float(position.realized_pnl or 0.0)
                        + float(realized_pnl)
                        - float(cost.total_cost)
                )

                position.market_price = fill_price
                position.updated_at = datetime.now(UTC)

                # ---------------------------------------
                # CASH MOVEMENT
                # ---------------------------------------
                fill_notional = fill_qty * fill_price
                total_cost = float(cost.total_cost)

                if side_norm == "buy":
                    cash_amount = -(fill_notional + total_cost)
                    entry_type = "buy"
                elif side_norm == "sell":
                    cash_amount = fill_notional - total_cost
                    entry_type = "sell"
                else:
                    cash_amount = 0.0
                    entry_type = "unknown"

                # ---------------------------------------
                # CLOSED TRADE (SAFE)
                # ---------------------------------------
                if side_norm == "sell" and prior_qty > 0:
                    closed_qty = min(fill_qty, prior_qty)

                    if closed_qty > 0:
                        gross_pnl = (fill_price - prior_avg_cost) * closed_qty
                        net_pnl = gross_pnl - total_cost

                        opened_at = prior_updated_at
                        closed_at = datetime.now(UTC)

                        holding_period_days = 0.0
                        if opened_at:
                            holding_period_days = max(
                                0.0,
                                (closed_at - opened_at).total_seconds() / 86400.0,
                            )

                        self.closed_trade_service.record_closed_trade(
                            portfolio_id=portfolio_id,
                            symbol=symbol_norm,
                            opened_at=opened_at,
                            closed_at=closed_at,
                            entry_qty=closed_qty,
                            exit_qty=closed_qty,
                            entry_price=prior_avg_cost,
                            exit_price=fill_price,
                            gross_pnl=gross_pnl,
                            net_pnl=net_pnl,
                            commission=float(cost.commission),
                            slippage=float(cost.slippage),
                            holding_period_days=holding_period_days,
                            side_open="buy",
                            side_close="sell",
                            notes=f"Closed trade from SELL {symbol_norm}",
                        )

                # ---------------------------------------
                # CASH LEDGER
                # ---------------------------------------
                self.accounting.record_cash_entry(
                    portfolio_id=portfolio_id,
                    entry_type=entry_type,
                    amount=float(cash_amount),
                    trade_order_id=order.id,
                    notes=f"{side_norm.upper()} {symbol_norm}",
                )

                self.db.commit()
                self.accounting.record_snapshot(portfolio_id)
                return order

            self.db.commit()
            self.accounting.record_snapshot(portfolio_id)
            return order

        except Exception:
            self.db.rollback()
            raise

