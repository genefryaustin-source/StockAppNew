from __future__ import annotations

import pandas as pd

from modules.portfolio.order_service import OrderService


class EventProcessor:
    def __init__(
        self,
        db_session,
        broker,
        market_data_service,
        constructor,
        guardrails,
        monitoring_service=None,
        alert_service=None,
    ):
        self.db = db_session
        self.broker = broker
        self.market_data_service = market_data_service
        self.constructor = constructor
        self.guardrails = guardrails
        self.monitoring_service = monitoring_service
        self.alert_service = alert_service

    def _build_price_map(self, symbols: list[str], df_pos: pd.DataFrame | None = None) -> dict[str, float]:
        prices: dict[str, float] = {}

        if df_pos is not None and not df_pos.empty and "Symbol" in df_pos.columns:
            for _, row in df_pos.iterrows():
                sym = row.get("Symbol")
                px = row.get("Market Price")
                if sym and px is not None:
                    prices[str(sym).upper()] = float(px)

        for sym in symbols:
            sym = str(sym).upper()
            if sym in prices:
                continue
            try:
                q = self.market_data_service.get_quote(sym)
                if isinstance(q, dict):
                    for key in ("price", "c", "last", "close", "regularMarketPrice"):
                        val = q.get(key)
                        if val is not None:
                            prices[sym] = float(val)
                            break
            except Exception:
                continue

        return prices

    def process_event(
        self,
        event: dict,
        portfolio_id: int,
        user_id: int | None,
        totals: dict,
        df_pos: pd.DataFrame,
        trading_cfg: dict,
        auto_execute: bool = False,
    ) -> dict:
        if not event:
            return {"status": "ignored", "message": "No event"}

        event_type = event.get("event_type")
        payload = event.get("payload", {})

        if event_type == "alert":
            if self.monitoring_service:
                self.monitoring_service.log_event(
                    event_type="event_alert",
                    status="processed",
                    message=payload.get("message", ""),
                    portfolio_id=portfolio_id,
                )
            return {"status": "processed", "message": "Alert event processed"}

        if event_type != "rebalance_required":
            return {"status": "ignored", "message": f"Unsupported event type: {event_type}"}

        target_records = payload.get("target_df", [])
        target_df = pd.DataFrame(target_records)

        if target_df.empty or "Symbol" not in target_df.columns or "Target Weight" not in target_df.columns:
            return {"status": "ignored", "message": "Invalid target payload"}

        prices = self._build_price_map(
            symbols=target_df["Symbol"].astype(str).tolist(),
            df_pos=df_pos,
        )

        rebalance_df = self.constructor.generate_rebalance_trades(
            target_df=target_df,
            prices=prices,
            portfolio_value=float(totals.get("equity", 0.0)),
        )

        if rebalance_df.empty:
            return {"status": "processed", "message": "No rebalance trades required", "rebalance_df": rebalance_df}

        valid, reasons = self.guardrails.validate_rebalance_plan(
            portfolio_id=portfolio_id,
            rebalance_df=rebalance_df,
            positions_df=df_pos if df_pos is not None else pd.DataFrame(),
            equity=float(totals.get("equity", 0.0)),
            config=trading_cfg,
        )

        if not valid:
            if self.alert_service:
                self.alert_service.push(
                    level="warning",
                    title="Event execution blocked",
                    message=" | ".join(reasons),
                    source="event_processor",
                    metadata={"portfolio_id": portfolio_id},
                )
            if self.monitoring_service:
                self.monitoring_service.log_event(
                    event_type="event_rebalance",
                    status="blocked",
                    message=" | ".join(reasons),
                    portfolio_id=portfolio_id,
                )
            return {
                "status": "blocked",
                "message": "Blocked by guardrails",
                "reasons": reasons,
                "rebalance_df": rebalance_df,
            }

        if not auto_execute:
            return {
                "status": "planned",
                "message": "Rebalance plan created",
                "rebalance_df": rebalance_df,
            }

        service = OrderService(self.db, self.broker, self.market_data_service)

        for _, row in rebalance_df.iterrows():
            service.submit_order(
                portfolio_id=portfolio_id,
                user_id=user_id,
                symbol=str(row["Symbol"]).upper(),
                side=str(row["Side"]).lower(),
                qty=float(row["Qty"]),
                order_type="market",
                tif="day",
            )

        if self.alert_service:
            self.alert_service.push(
                level="info",
                title="Event rebalance executed",
                message=f"Executed {len(rebalance_df)} trades",
                source="event_processor",
                metadata={"portfolio_id": portfolio_id},
            )

        if self.monitoring_service:
            self.monitoring_service.log_event(
                event_type="event_rebalance",
                status="executed",
                message=f"Executed {len(rebalance_df)} trades",
                portfolio_id=portfolio_id,
            )

        return {
            "status": "executed",
            "message": "Rebalance executed",
            "rebalance_df": rebalance_df,
        }