from __future__ import annotations

from datetime import datetime, UTC

from models.trading import ClosedTrade


class ClosedTradeService:
    def __init__(self, db_session):
        self.db = db_session

    def record_closed_trade(
        self,
        portfolio_id: int,
        symbol: str,
        opened_at,
        closed_at,
        entry_qty: float,
        exit_qty: float,
        entry_price: float,
        exit_price: float,
        gross_pnl: float,
        net_pnl: float,
        commission: float,
        slippage: float,
        holding_period_days: float,
        side_open: str,
        side_close: str,
        notes: str | None = None,
    ) -> ClosedTrade:
        row = ClosedTrade(
            portfolio_id=portfolio_id,
            symbol=symbol.upper(),
            opened_at=opened_at,
            closed_at=closed_at or datetime.now(UTC),
            entry_qty=float(entry_qty),
            exit_qty=float(exit_qty),
            entry_price=float(entry_price),
            exit_price=float(exit_price),
            gross_pnl=float(gross_pnl),
            net_pnl=float(net_pnl),
            commission=float(commission),
            slippage=float(slippage),
            holding_period_days=float(holding_period_days),
            side_open=side_open,
            side_close=side_close,
            notes=notes,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row