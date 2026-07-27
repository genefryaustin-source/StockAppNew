from __future__ import annotations

import threading
import time
import pandas as pd

from modules.portfolio.automation_service import PortfolioAutomationService
from modules.portfolio.strategy_run_service import StrategyRunService
from modules.portfolio.guardrail_service import GuardrailService
from modules.portfolio.alert_service import AlertService
from modules.portfolio.monitoring_service import MonitoringService
from modules.analytics.strategy_service import list_discovered_strategies
from modules.portfolio.strategy_bridge import StrategyBridge
from modules.portfolio.order_service import OrderService

import streamlit as st


def _safe_price(q):
    if not isinstance(q, dict):
        return None
    for k in ("price", "c", "last", "close"):
        v = q.get(k)
        if v is not None:
            try:
                return float(v)
            except Exception:
                continue
    return None


class PortfolioScheduler:
    def __init__(
        self,
        db_session,
        market_data_service,
        constructor,
        user_id,
        broker,
        alert_service=None,
        monitoring_service=None,
    ):
        self.db = db_session
        self.market_data_service = market_data_service
        self.constructor = constructor
        self.user_id = user_id
        self.broker = broker

        self.alert_service = alert_service or AlertService()
        self.monitoring_service = monitoring_service or MonitoringService()

        self.running = False
        self.thread = None

    # ---------------------------------
    def start(self, interval_seconds=60):
        if self.running:
            return

        self.running = True

        self.thread = threading.Thread(
            target=self._run_loop,
            args=(interval_seconds,),
            daemon=True,
        )
        self.thread.start()

    # ---------------------------------
    def stop(self):
        self.running = False

    # ---------------------------------
    def _run_loop(self, interval_seconds):
        automation = PortfolioAutomationService(self.constructor)
        run_service = StrategyRunService(self.db)

        while self.running:
            try:
                self.monitoring_service.heartbeat("running", "Cycle starting")

                self._process_cycle(automation, run_service)

                self.monitoring_service.heartbeat("ok", "Cycle completed")

            except Exception as e:
                print("SCHEDULER ERROR:", e)

                self.monitoring_service.heartbeat("error", str(e))
                self.monitoring_service.log_event(
                    event_type="scheduler_cycle",
                    status="error",
                    message=str(e),
                )

                self.alert_service.push(
                    level="error",
                    title="Scheduler cycle failed",
                    message=str(e),
                    source="scheduler",
                )

            time.sleep(interval_seconds)

    # ---------------------------------
    def _process_cycle(self, automation, run_service):

        strategies = list_discovered_strategies(self.db, self.user_id)

        if not strategies:
            return

        bridge = StrategyBridge(self.db, self.user_id)
        guardrails = GuardrailService(self.db)
        trading_cfg = st.secrets.get("trading", {})

        for strat in strategies:
            try:
                target_df = bridge.load_strategy_to_weights(strat)

                if target_df is None or target_df.empty:
                    continue

                if "Symbol" not in target_df.columns:
                    continue

                prices = {}

                for sym in target_df["Symbol"]:
                    try:
                        q = self.market_data_service.get_quote(sym)
                        px = _safe_price(q)
                        if px is not None:
                            prices[sym] = px
                    except Exception:
                        continue

                portfolio_value = 100000.0  # TODO: replace

                result = automation.generate_rebalance_if_needed(
                    target_df=target_df,
                    prices=prices,
                    portfolio_value=portfolio_value,
                    drift_threshold=0.05,
                )

                if not result.get("triggered"):
                    continue

                rebalance_df = result.get("rebalance_df")

                if rebalance_df is None or rebalance_df.empty:
                    continue

                from models.trading import PortfolioPosition

                positions = (
                    self.db.query(PortfolioPosition)
                    .filter(PortfolioPosition.portfolio_id == strat.portfolio_id)
                    .all()
                )

                db_positions_df = pd.DataFrame([
                    {
                        "Symbol": p.symbol,
                        "Qty": p.qty
                    }
                    for p in positions
                ])

                valid, reasons = guardrails.validate_rebalance_plan(
                    portfolio_id=strat.portfolio_id,
                    rebalance_df=rebalance_df,
                    positions_df=positions_df,
                    equity=float(portfolio_value),
                    config=trading_cfg,
                )

                if not valid:
                    msg = " | ".join(reasons)

                    self.alert_service.push(
                        level="warning",
                        title=f"Guardrail block: {strat.name}",
                        message=msg,
                        source="guardrails",
                    )

                    run_service.log_run(
                        portfolio_id=strat.portfolio_id,
                        strategy_name=strat.name,
                        trigger_type="scheduled",
                        status="blocked",
                        target_df=target_df,
                        drift_threshold=0.05,
                        notes=msg,
                    )
                    continue
                # ---------------------------------
                # RECONCILIATION STEP (NEW)
                # ---------------------------------
                from modules.portfolio.reconciliation_service import ReconciliationService

                recon = ReconciliationService(self.db, self.broker)

                try:
                    # Get current DB positions from constructor
                    db_positions_df = getattr(self.constructor, "positions_df", pd.DataFrame())

                    pos_diff = recon.reconcile_positions(db_positions_df)

                    if not pos_diff.empty:
                        msg = f"{len(pos_diff)} position mismatches detected"

                        print("RECON WARNING:", msg)

                        self.alert_service.push(
                            level="warning",
                            title="Position Reconciliation Mismatch",
                            message=msg,
                            source="reconciliation",
                            metadata={"portfolio_id": strat.portfolio_id},
                        )

                        self.monitoring_service.log_event(
                            event_type="reconciliation",
                            status="mismatch",
                            message=msg,
                            portfolio_id=strat.portfolio_id,
                            metadata={"rows": len(pos_diff)},
                        )

                except Exception as recon_err:
                    print("RECON ERROR:", recon_err)

                    self.alert_service.push(
                        level="error",
                        title="Reconciliation Failed",
                        message=str(recon_err),
                        source="reconciliation",
                    )

                AUTO_EXECUTE = False

                if AUTO_EXECUTE:
                    service = OrderService(self.db, self.broker, self.market_data_service)

                    for _, row in rebalance_df.iterrows():
                        service.submit_order(
                            portfolio_id=strat.portfolio_id,
                            user_id=self.user_id,
                            symbol=row["Symbol"],
                            side=row["Side"],
                            qty=float(row["Qty"]),
                            order_type="market",
                            tif="day",
                        )

                    status = "executed"
                else:
                    status = "planned"

                run_service.log_run(
                    portfolio_id=strat.portfolio_id,
                    strategy_name=strat.name,
                    trigger_type="scheduled",
                    status=status,
                    target_df=target_df,
                    drift_threshold=0.05,
                    notes="Scheduled cycle",
                )

            except Exception as e:
                print("Strategy error:", e)

                self.alert_service.push(
                    level="error",
                    title=f"Strategy error: {strat.name}",
                    message=str(e),
                    source="scheduler",
                )