"""
modules/forex/forex_end_to_end_test_harness.py

End-to-end validation harness for the Forex subsystem.

This harness runs realistic workflow checks across:
- Provider / price infrastructure
- Analytics engines
- Strategy and AI layers
- Portfolio / execution / journal layers
- Platform controllers and terminal APIs
- Dashboard imports / render entry points

It is intentionally tolerant of unavailable live providers, API keys, or DB
connections. The goal is to detect integration breakage without requiring live
market connectivity for every test run.
"""

from __future__ import annotations

import importlib
import time
import traceback
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional


@dataclass
class E2ETestResult:
    layer: str
    workflow: str
    status: str
    passed: bool
    duration_ms: float
    message: str
    details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ForexEndToEndTestHarness:
    def __init__(
        self,
        db=None,
        run_live_provider_checks: bool = False,
        execute_paper_trade: bool = False,
    ):
        self.db = db
        self.run_live_provider_checks = bool(run_live_provider_checks)
        self.execute_paper_trade = bool(execute_paper_trade)
        self.results: List[E2ETestResult] = []

    # ------------------------------------------------------------------
    # Public runner
    # ------------------------------------------------------------------

    def run_all(self) -> Dict[str, Any]:
        self.results = []

        workflows = [
            ("Infrastructure", "Registry Bootstraps", self.test_registry),
            ("Infrastructure", "Runtime Manager Starts", self.test_runtime_manager),
            ("Infrastructure", "Control Plane Status", self.test_control_plane),
            ("Infrastructure", "Provider Health Summary", self.test_provider_health),
            ("Infrastructure", "Price Service Loads", self.test_price_service),

            ("Data Layer", "Quote Refresh Engine Loads", self.test_refresh_engine),
            ("Data Layer", "Bulk Refresh Engine Loads", self.test_bulk_refresh_engine),
            ("Data Layer", "Database Cache Loads", self.test_database_cache),
            ("Data Layer", "Telemetry Loads", self.test_provider_telemetry),

            ("Analytics", "Currency Strength Workflow", self.test_currency_strength_workflow),
            ("Analytics", "Macro Regime Workflow", self.test_macro_regime_workflow),
            ("Analytics", "Central Bank Workflow", self.test_central_bank_workflow),
            ("Analytics", "Sentiment Workflow", self.test_sentiment_workflow),
            ("Analytics", "Carry Trade Workflow", self.test_carry_trade_workflow),
            ("Analytics", "Institutional Scanner Workflow", self.test_institutional_workflow),
            ("Analytics", "Alpha Model Workflow", self.test_alpha_model_workflow),
            ("Analytics", "Command Center Workflow", self.test_command_center_workflow),

            ("Trading", "Portfolio Manager Workflow", self.test_portfolio_manager_workflow),
            ("Trading", "Order Management Workflow", self.test_order_management_workflow),
            ("Trading", "Trade Execution Workflow", self.test_trade_execution_workflow),
            ("Trading", "Risk Management Workflow", self.test_risk_management_workflow),
            ("Trading", "Performance Analytics Workflow", self.test_performance_workflow),
            ("Trading", "Trade Journal Workflow", self.test_trade_journal_workflow),

            ("Strategy", "Strategy Engine Workflow", self.test_strategy_engine_workflow),
            ("Strategy", "Strategy Lab Workflow", self.test_strategy_lab_workflow),
            ("Strategy", "Portfolio Optimizer Workflow", self.test_portfolio_optimizer_workflow),
            ("Strategy", "Autonomous Trader Workflow", self.test_autonomous_trader_workflow),

            ("AI", "AI Assistant Workflow", self.test_ai_assistant_workflow),
            ("AI", "AI Orchestrator Workflow", self.test_ai_orchestrator_workflow),
            ("AI", "Command Processor Workflow", self.test_command_processor_workflow),

            ("Platform", "Operations Center Workflow", self.test_operations_center_workflow),
            ("Platform", "Supervisor Workflow", self.test_supervisor_workflow),
            ("Platform", "Master Controller Workflow", self.test_master_controller_workflow),
            ("Platform", "Enterprise Workspace Workflow", self.test_enterprise_workspace_workflow),
            ("Platform", "Institutional Workspace Workflow", self.test_institutional_workspace_workflow),
            ("Platform", "Execution Center Workflow", self.test_execution_center_workflow),
            ("Platform", "Trading Desk Workflow", self.test_trading_desk_workflow),
            ("Platform", "Institutional Terminal Workflow", self.test_institutional_terminal_workflow),
            ("Platform", "Terminal API Workflow", self.test_terminal_api_workflow),

            ("UI", "Terminal Dashboard Imports", self.test_terminal_dashboard_import),
            ("UI", "Trading Desk Dashboard Imports", self.test_trading_desk_dashboard_import),
            ("UI", "Execution Dashboard Imports", self.test_execution_dashboard_import),
            ("UI", "Portfolio Dashboard Imports", self.test_portfolio_dashboard_import),
            ("UI", "Order Dashboard Imports", self.test_order_dashboard_import),
            ("UI", "AI Dashboard Imports", self.test_ai_dashboard_import),
            ("UI", "Workspace Imports", self.test_workspace_import),
            ("UI", "App Integration Imports", self.test_app_integration_import),
            ("UI", "App Router Imports", self.test_app_router_import),
            ("UI", "Forex Module Imports", self.test_forex_module_import),
        ]

        if self.run_live_provider_checks:
            workflows.extend([
                ("Live Providers", "Frankfurter Health", lambda: self.test_provider("frankfurter_provider")),
                ("Live Providers", "ECB Health", lambda: self.test_provider("ecb_provider")),
                ("Live Providers", "ExchangeRate.host Health", lambda: self.test_provider("exchangerate_provider")),
                ("Live Providers", "Yahoo Health", lambda: self.test_provider("yahoo_forex_provider")),
                ("Live Providers", "TwelveData Health", lambda: self.test_provider("twelvedata_forex_provider")),
                ("Live Providers", "Alpha Vantage Health", lambda: self.test_provider("alpha_vantage_forex_provider")),
                ("Live Providers", "Finnhub Health", lambda: self.test_provider("finnhub_forex_provider")),
                ("Live Providers", "Polygon Health", lambda: self.test_provider("polygon_forex_provider")),
            ])

        for layer, workflow, fn in workflows:
            self._run(layer, workflow, fn)

        return self.report()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run(self, layer: str, workflow: str, fn: Callable[[], Any]) -> None:
        start = time.perf_counter()
        try:
            details = fn()
            duration = (time.perf_counter() - start) * 1000.0
            self.results.append(E2ETestResult(
                layer=layer,
                workflow=workflow,
                status="PASS",
                passed=True,
                duration_ms=round(duration, 2),
                message="OK",
                details=details if isinstance(details, dict) else {"result": str(details)},
            ))
        except Exception as exc:
            duration = (time.perf_counter() - start) * 1000.0
            self.results.append(E2ETestResult(
                layer=layer,
                workflow=workflow,
                status="FAIL",
                passed=False,
                duration_ms=round(duration, 2),
                message=str(exc),
                details={"traceback": traceback.format_exc(limit=6)},
            ))

    def _import(self, module: str):
        return importlib.import_module(module)

    def _factory(self, module: str, factory: str, pass_db: bool = False):
        mod = self._import(module)
        fn = getattr(mod, factory)
        try:
            return fn(self.db) if pass_db else fn()
        except TypeError:
            return fn()

    def _assert_dict(self, value: Any, name: str) -> Dict[str, Any]:
        if not isinstance(value, dict):
            raise AssertionError(f"{name} did not return a dict.")
        return value

    def _compact(self, value: Any) -> Dict[str, Any]:
        if isinstance(value, dict):
            return {
                "keys": list(value.keys())[:25],
                "status": value.get("status"),
                "generated_at": value.get("generated_at"),
            }
        if isinstance(value, list):
            return {"list_len": len(value)}
        return {"type": type(value).__name__}

    # ------------------------------------------------------------------
    # Infrastructure
    # ------------------------------------------------------------------

    def test_registry(self):
        registry = self._factory("modules.forex.forex_registry", "get_forex_registry")
        summary = registry.summary()
        return self._assert_dict(summary, "registry.summary")

    def test_runtime_manager(self):
        runtime = self._factory("modules.forex.forex_runtime_manager", "get_forex_runtime_manager")
        status = runtime.status()
        return self._assert_dict(status, "runtime.status")

    def test_control_plane(self):
        cp = self._factory("modules.forex.forex_control_plane", "get_forex_control_plane", pass_db=True)
        return self._assert_dict(cp.status(), "control_plane.status")

    def test_provider_health(self):
        health = self._factory("modules.forex.forex_provider_health", "get_forex_provider_health")
        return self._assert_dict(health.summary(), "provider_health.summary")

    def test_price_service(self):
        service = self._factory("modules.forex.forex_price_service", "get_forex_price_service")
        return {"object_type": type(service).__name__, "loaded": service is not None}

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def test_refresh_engine(self):
        engine = self._factory("modules.forex.forex_refresh_engine", "get_forex_refresh_engine")
        return {"object_type": type(engine).__name__}

    def test_bulk_refresh_engine(self):
        engine = self._factory("modules.forex.forex_bulk_refresh_engine", "get_forex_bulk_refresh_engine")
        return {"object_type": type(engine).__name__}

    def test_database_cache(self):
        mod = self._import("modules.forex.forex_database_cache")
        cls = getattr(mod, "ForexDatabaseCache")
        return {"class": cls.__name__, "db_supplied": self.db is not None}

    def test_provider_telemetry(self):
        telem = self._factory("modules.forex.forex_provider_telemetry", "get_forex_provider_telemetry", pass_db=True)
        return {"object_type": type(telem).__name__}

    def test_provider(self, provider_module: str):
        mod = self._import(f"modules.forex.providers.{provider_module}")
        hc = getattr(mod, "health_check", None)
        if callable(hc):
            return hc()
        return {"module": provider_module, "health_check": False}

    # ------------------------------------------------------------------
    # Analytics workflows
    # ------------------------------------------------------------------

    def test_currency_strength_workflow(self):
        engine = self._factory("modules.forex.forex_currency_strength_engine", "get_forex_currency_strength_engine")
        data = engine.command_center_payload(force_refresh=False)
        return self._compact(data)

    def test_macro_regime_workflow(self):
        engine = self._factory("modules.forex.forex_macro_regime_engine", "get_forex_macro_regime_engine")
        data = engine.analyze(force_refresh=False)
        return self._compact(data)

    def test_central_bank_workflow(self):
        engine = self._factory("modules.forex.forex_central_bank_engine", "get_forex_central_bank_engine")
        data = engine.analyze()
        return self._compact(data)

    def test_sentiment_workflow(self):
        engine = self._factory("modules.forex.forex_sentiment_engine", "get_forex_sentiment_engine")
        data = engine.analyze(force_refresh=False)
        return self._compact(data)

    def test_carry_trade_workflow(self):
        engine = self._factory("modules.forex.forex_carry_trade_engine", "get_forex_carry_trade_engine")
        data = engine.analyze(force_refresh=False)
        return self._compact(data)

    def test_institutional_workflow(self):
        engine = self._factory("modules.forex.forex_institutional_scanner", "get_forex_institutional_scanner")
        data = engine.scan(force_refresh=False)
        return self._compact(data)

    def test_alpha_model_workflow(self):
        engine = self._factory("modules.forex.forex_alpha_model", "get_forex_alpha_model")
        data = engine.command_center_payload(force_refresh=False)
        return self._compact(data)

    def test_command_center_workflow(self):
        engine = self._factory("modules.forex.forex_command_center_engine", "get_forex_command_center_engine")
        data = engine.build(force_refresh=False)
        return self._compact(data)

    # ------------------------------------------------------------------
    # Trading workflows
    # ------------------------------------------------------------------

    def test_portfolio_manager_workflow(self):
        manager = self._factory("modules.forex.forex_portfolio_manager", "get_forex_portfolio_manager", pass_db=True)
        data = manager.portfolio_summary(positions=[])
        return self._compact(data)

    def test_order_management_workflow(self):
        engine = self._factory("modules.forex.forex_order_management_engine", "get_forex_order_management_engine", pass_db=True)
        return {
            "object_type": type(engine).__name__,
            "open_orders_len": len(engine.open_orders()),
            "filled_orders_len": len(engine.filled_orders()),
        }

    def test_trade_execution_workflow(self):
        engine = self._factory("modules.forex.forex_trade_execution_engine", "get_forex_trade_execution_engine", pass_db=True)
        if not self.execute_paper_trade:
            return {"object_type": type(engine).__name__, "paper_trade_execution": "skipped"}
        result = engine.submit_order(pair="EUR/USD", side="BUY", units=1000, broker="paper")
        return self._compact(result)

    def test_risk_management_workflow(self):
        engine = self._factory("modules.forex.forex_risk_management_engine", "get_forex_risk_management_engine", pass_db=True)
        data = engine.analyze(positions=[])
        return self._compact(data)

    def test_performance_workflow(self):
        engine = self._factory("modules.forex.forex_performance_analytics_engine", "get_forex_performance_analytics_engine", pass_db=True)
        data = engine.analyze(positions=[])
        return self._compact(data)

    def test_trade_journal_workflow(self):
        engine = self._factory("modules.forex.forex_trade_journal_engine", "get_forex_trade_journal_engine", pass_db=True)
        data = engine.summarize(limit=25)
        return self._compact(data)

    # ------------------------------------------------------------------
    # Strategy / AI workflows
    # ------------------------------------------------------------------

    def test_strategy_engine_workflow(self):
        engine = self._factory("modules.forex.forex_strategy_engine", "get_forex_strategy_engine", pass_db=True)
        data = engine.generate_trade_plan(force_refresh=False)
        return self._compact(data)

    def test_strategy_lab_workflow(self):
        lab = self._factory("modules.forex.forex_strategy_lab", "get_forex_strategy_lab", pass_db=True)
        data = lab.run(force_refresh=False)
        return self._compact(data)

    def test_portfolio_optimizer_workflow(self):
        opt = self._factory("modules.forex.forex_portfolio_optimizer", "get_forex_portfolio_optimizer", pass_db=True)
        data = opt.optimize(max_positions=3)
        return self._compact(data)

    def test_autonomous_trader_workflow(self):
        trader = self._factory("modules.forex.forex_autonomous_trader", "get_forex_autonomous_trader", pass_db=True)
        if not self.execute_paper_trade:
            return {"object_type": type(trader).__name__, "autonomous_execution": "skipped"}
        data = trader.run_cycle()
        return self._compact(data)

    def test_ai_assistant_workflow(self):
        ai = self._factory("modules.forex.forex_ai_assistant", "get_forex_ai_assistant", pass_db=True)
        data = ai.daily_briefing()
        return self._compact(data)

    def test_ai_orchestrator_workflow(self):
        orch = self._factory("modules.forex.forex_ai_orchestrator", "get_forex_ai_orchestrator", pass_db=True)
        data = orch.morning_brief()
        return self._compact(data)

    def test_command_processor_workflow(self):
        proc = self._factory("modules.forex.forex_command_processor", "get_forex_command_processor", pass_db=True)
        data = proc.execute("command_center")
        return self._compact(data)

    # ------------------------------------------------------------------
    # Platform workflows
    # ------------------------------------------------------------------

    def test_operations_center_workflow(self):
        obj = self._factory("modules.forex.forex_operations_center", "get_forex_operations_center", pass_db=True)
        return self._compact(obj.dashboard())

    def test_supervisor_workflow(self):
        obj = self._factory("modules.forex.forex_supervisor", "get_forex_supervisor", pass_db=True)
        return self._compact(obj.heartbeat())

    def test_master_controller_workflow(self):
        obj = self._factory("modules.forex.forex_master_controller", "get_forex_master_controller", pass_db=True)
        return self._compact(obj.system_snapshot())

    def test_enterprise_workspace_workflow(self):
        obj = self._factory("modules.forex.forex_enterprise_workspace", "get_forex_enterprise_workspace", pass_db=True)
        return self._compact(obj.workspace_snapshot())

    def test_institutional_workspace_workflow(self):
        obj = self._factory("modules.forex.forex_institutional_workspace", "get_forex_institutional_workspace", pass_db=True)
        return self._compact(obj.snapshot())

    def test_execution_center_workflow(self):
        obj = self._factory("modules.forex.forex_execution_center", "get_forex_execution_center", pass_db=True)
        return self._compact(obj.dashboard())

    def test_trading_desk_workflow(self):
        obj = self._factory("modules.forex.forex_trading_desk", "get_forex_trading_desk", pass_db=True)
        return self._compact(obj.dashboard())

    def test_institutional_terminal_workflow(self):
        obj = self._factory("modules.forex.forex_institutional_terminal", "get_forex_institutional_terminal", pass_db=True)
        return self._compact(obj.snapshot())

    def test_terminal_api_workflow(self):
        obj = self._factory("modules.forex.forex_terminal_api", "get_forex_terminal_api", pass_db=True)
        return self._compact(obj.get_terminal_snapshot())

    # ------------------------------------------------------------------
    # UI import checks
    # ------------------------------------------------------------------

    def _ui_import(self, module: str, factory: str):
        obj = self._factory(module, factory, pass_db=True)
        return {"module": module, "factory": factory, "object_type": type(obj).__name__}

    def test_terminal_dashboard_import(self): return self._ui_import("modules.forex.forex_terminal_dashboard", "get_forex_terminal_dashboard")
    def test_trading_desk_dashboard_import(self): return self._ui_import("modules.forex.forex_trading_desk_dashboard", "get_forex_trading_desk_dashboard")
    def test_execution_dashboard_import(self): return self._ui_import("modules.forex.forex_execution_dashboard", "get_forex_execution_dashboard")
    def test_portfolio_dashboard_import(self): return self._ui_import("modules.forex.forex_portfolio_dashboard", "get_forex_portfolio_dashboard")
    def test_order_dashboard_import(self): return self._ui_import("modules.forex.forex_order_dashboard", "get_forex_order_dashboard")
    def test_ai_dashboard_import(self): return self._ui_import("modules.forex.forex_ai_dashboard", "get_forex_ai_dashboard")
    def test_workspace_import(self): return self._ui_import("modules.forex.forex_workspace", "get_forex_workspace")
    def test_app_integration_import(self): return self._factory("ui.forex.forex_app_integration", "get_forex_app_integration", pass_db=True).__class__.__name__
    def test_app_router_import(self): return self._ui_import("modules.forex.forex_app_router", "get_forex_app_router")
    def test_forex_module_import(self): return self._ui_import("modules.forex.forex_module", "get_forex_module")

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def report(self) -> Dict[str, Any]:
        rows = [r.to_dict() for r in self.results]
        passed = sum(1 for r in self.results if r.passed)
        failed = len(self.results) - passed

        by_layer: Dict[str, Dict[str, int]] = {}
        for r in self.results:
            row = by_layer.setdefault(r.layer, {"total": 0, "passed": 0, "failed": 0})
            row["total"] += 1
            if r.passed:
                row["passed"] += 1
            else:
                row["failed"] += 1

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "READY_FOR_PRODUCTION" if failed == 0 else "NEEDS_ATTENTION",
            "total_tests": len(self.results),
            "passed": passed,
            "failed": failed,
            "by_layer": by_layer,
            "results": rows,
            "text_report": self.text_report(),
        }

    def text_report(self) -> str:
        passed = sum(1 for r in self.results if r.passed)
        failed = len(self.results) - passed
        layers = []
        for r in self.results:
            if r.layer not in layers:
                layers.append(r.layer)

        lines = [
            "==========================================",
            "FOREX END-TO-END VALIDATION",
            "==========================================",
            "",
        ]

        for layer in layers:
            layer_results = [r for r in self.results if r.layer == layer]
            layer_failed = sum(1 for r in layer_results if not r.passed)
            status = "PASS" if layer_failed == 0 else "FAIL"
            lines.append(f"{layer:<30} {status}")

        lines.extend([
            "",
            f"Modules / Workflows Tested : {len(self.results)}",
            f"Passed                     : {passed}",
            f"Failed                     : {failed}",
            "",
            "READY FOR PRODUCTION" if failed == 0 else "NEEDS ATTENTION",
        ])

        if failed:
            lines.append("")
            lines.append("Failures:")
            for r in self.results:
                if not r.passed:
                    lines.append(f"- {r.layer} / {r.workflow}: {r.message}")

        return "\n".join(lines)


def run_forex_end_to_end_test_harness(
    db=None,
    run_live_provider_checks: bool = False,
    execute_paper_trade: bool = False,
) -> Dict[str, Any]:
    return ForexEndToEndTestHarness(
        db=db,
        run_live_provider_checks=run_live_provider_checks,
        execute_paper_trade=execute_paper_trade,
    ).run_all()


def render_forex_end_to_end_test_harness(db=None):
    report = run_forex_end_to_end_test_harness(db=db)

    try:
        import streamlit as st
        import pandas as pd
    except Exception:
        return report

    st.title("Forex End-to-End Test Harness")

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Workflows", report["total_tests"])
    c2.metric("Passed", report["passed"])
    c3.metric("Failed", report["failed"])

    if report["failed"] == 0:
        st.success("Forex end-to-end validation passed.")
    else:
        st.error("Forex end-to-end validation found issues.")

    st.code(report["text_report"])
    st.dataframe(pd.DataFrame(report["results"]), use_container_width=True, hide_index=True)
    return report
