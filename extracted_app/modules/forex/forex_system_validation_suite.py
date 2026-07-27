"""
modules/forex/forex_system_validation_suite.py

End-to-end validation suite for the Forex subsystem.
"""

from __future__ import annotations

import importlib
import traceback
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional


@dataclass
class ForexValidationResult:
    category: str
    name: str
    status: str
    passed: bool
    message: str
    duration_ms: float = 0.0
    details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ForexSystemValidationSuite:
    def __init__(self, db=None, run_live_provider_checks: bool = False):
        self.db = db
        self.run_live_provider_checks = bool(run_live_provider_checks)
        self.results: List[ForexValidationResult] = []

    def run_all(self) -> Dict[str, Any]:
        self.results = []

        checks = [
            ("Providers", "Provider Router Import", self.validate_provider_router),
            ("Providers", "Price Service Import", self.validate_price_service),
            ("Providers", "Provider Health Import", self.validate_provider_health),
            ("Providers", "Provider Telemetry Import", self.validate_provider_telemetry),
            ("Providers", "Refresh Engine Import", self.validate_refresh_engine),
            ("Providers", "Bulk Refresh Import", self.validate_bulk_refresh_engine),

            ("Analytics", "Currency Strength Engine", self.validate_currency_strength),
            ("Analytics", "Alpha Model", self.validate_alpha_model),
            ("Analytics", "Carry Trade Engine", self.validate_carry_trade),
            ("Analytics", "Central Bank Engine", self.validate_central_bank),
            ("Analytics", "Sentiment Engine", self.validate_sentiment),
            ("Analytics", "Macro Regime Engine", self.validate_macro_regime),
            ("Analytics", "Institutional Scanner", self.validate_institutional_scanner),
            ("Analytics", "Command Center Engine", self.validate_command_center),

            ("Execution", "Portfolio Manager", self.validate_portfolio_manager),
            ("Execution", "Trade Execution Engine", self.validate_trade_execution),
            ("Execution", "Order Management Engine", self.validate_order_management),
            ("Execution", "Risk Management Engine", self.validate_risk_management),
            ("Execution", "Performance Analytics Engine", self.validate_performance),
            ("Execution", "Trade Journal Engine", self.validate_trade_journal),
            ("Execution", "Strategy Engine", self.validate_strategy_engine),
            ("Execution", "Strategy Lab", self.validate_strategy_lab),
            ("Execution", "Portfolio Optimizer", self.validate_portfolio_optimizer),
            ("Execution", "Autonomous Trader", self.validate_autonomous_trader),

            ("Platform", "AI Assistant", self.validate_ai_assistant),
            ("Platform", "AI Orchestrator", self.validate_ai_orchestrator),
            ("Platform", "Command Processor", self.validate_command_processor),
            ("Platform", "Control Plane", self.validate_control_plane),
            ("Platform", "Operations Center", self.validate_operations_center),
            ("Platform", "Supervisor", self.validate_supervisor),
            ("Platform", "Master Controller", self.validate_master_controller),
            ("Platform", "Enterprise Workspace", self.validate_enterprise_workspace),
            ("Platform", "Institutional Workspace", self.validate_institutional_workspace),
            ("Platform", "Execution Center", self.validate_execution_center),
            ("Platform", "Trading Desk", self.validate_trading_desk),
            ("Platform", "Institutional Terminal", self.validate_institutional_terminal),
            ("Platform", "Terminal API", self.validate_terminal_api),
            ("Platform", "Terminal Dashboard Service", self.validate_terminal_dashboard_service),
            ("Platform", "Terminal Controller", self.validate_terminal_controller),
            ("Platform", "Terminal Router", self.validate_terminal_router),
            ("Platform", "Terminal Bridge", self.validate_terminal_bridge),
            ("Platform", "Streamlit Adapter", self.validate_streamlit_adapter),
            ("Platform", "App Adapter", self.validate_app_adapter),
            ("Platform", "UI Integration", self.validate_ui_integration),
            ("Platform", "Application", self.validate_application),
            ("Platform", "Bootstrap", self.validate_bootstrap),
            ("Platform", "App Router", self.validate_app_router),
            ("Platform", "Forex Module", self.validate_forex_module),

            ("Dashboards", "Terminal Dashboard", self.validate_terminal_dashboard),
            ("Dashboards", "Trading Desk Dashboard", self.validate_trading_desk_dashboard),
            ("Dashboards", "Execution Dashboard", self.validate_execution_dashboard),
            ("Dashboards", "Portfolio Dashboard", self.validate_portfolio_dashboard),
            ("Dashboards", "Order Dashboard", self.validate_order_dashboard),
            ("Dashboards", "AI Dashboard", self.validate_ai_dashboard),
            ("Dashboards", "Workspace", self.validate_workspace),
        ]

        if self.run_live_provider_checks:
            checks.extend([
                ("Live Providers", "Frankfurter", lambda: self.validate_provider_module("frankfurter_provider")),
                ("Live Providers", "ECB", lambda: self.validate_provider_module("ecb_provider")),
                ("Live Providers", "ExchangeRate.host", lambda: self.validate_provider_module("exchangerate_provider")),
                ("Live Providers", "Yahoo", lambda: self.validate_provider_module("yahoo_forex_provider")),
                ("Live Providers", "TwelveData", lambda: self.validate_provider_module("twelvedata_forex_provider")),
                ("Live Providers", "Alpha Vantage", lambda: self.validate_provider_module("alpha_vantage_forex_provider")),
                ("Live Providers", "Finnhub", lambda: self.validate_provider_module("finnhub_forex_provider")),
                ("Live Providers", "Polygon", lambda: self.validate_provider_module("polygon_forex_provider")),
            ])

        for category, name, fn in checks:
            self._run_check(category, name, fn)

        return self.report()

    def _run_check(self, category: str, name: str, fn: Callable[[], Any]) -> None:
        import time
        start = time.perf_counter()
        try:
            details = fn()
            duration = (time.perf_counter() - start) * 1000.0
            self.results.append(ForexValidationResult(
                category=category,
                name=name,
                status="PASSED",
                passed=True,
                message="OK",
                duration_ms=round(duration, 2),
                details=details if isinstance(details, dict) else {"result": str(details)},
            ))
        except Exception as exc:
            duration = (time.perf_counter() - start) * 1000.0
            self.results.append(ForexValidationResult(
                category=category,
                name=name,
                status="FAILED",
                passed=False,
                message=str(exc),
                duration_ms=round(duration, 2),
                details={"traceback": traceback.format_exc(limit=5)},
            ))

    def _import(self, module_path: str):
        return importlib.import_module(module_path)

    def _factory_check(self, module_path: str, factory_name: str) -> Dict[str, Any]:
        mod = self._import(module_path)
        factory = getattr(mod, factory_name)
        obj = factory(self.db) if "db" in getattr(factory, "__code__", object()).co_varnames else factory()
        return {
            "module": module_path,
            "factory": factory_name,
            "object_type": type(obj).__name__,
            "loaded": obj is not None,
        }

    def _function_check(self, module_path: str, function_name: str) -> Dict[str, Any]:
        mod = self._import(module_path)
        fn = getattr(mod, function_name)
        return {
            "module": module_path,
            "function": function_name,
            "callable": callable(fn),
        }

    # Providers
    def validate_provider_router(self): return self._factory_check("modules.forex.providers.forex_provider_router", "get_forex_provider_router")
    def validate_price_service(self): return self._factory_check("modules.forex.forex_price_service", "get_forex_price_service")
    def validate_provider_health(self): return self._factory_check("modules.forex.forex_provider_health", "get_forex_provider_health")
    def validate_provider_telemetry(self): return self._factory_check("modules.forex.forex_provider_telemetry", "get_forex_provider_telemetry")
    def validate_refresh_engine(self): return self._factory_check("modules.forex.forex_refresh_engine", "get_forex_refresh_engine")
    def validate_bulk_refresh_engine(self): return self._factory_check("modules.forex.forex_bulk_refresh_engine", "get_forex_bulk_refresh_engine")

    def validate_provider_module(self, name: str) -> Dict[str, Any]:
        mod = self._import(f"modules.forex.providers.{name}")
        health = getattr(mod, "health_check", None)
        if callable(health):
            return health()
        get_quote = getattr(mod, "get_quote", None)
        return {"provider_module": name, "get_quote_callable": callable(get_quote)}

    # Analytics
    def validate_currency_strength(self): return self._factory_check("modules.forex.forex_currency_strength_engine", "get_forex_currency_strength_engine")
    def validate_alpha_model(self): return self._factory_check("modules.forex.forex_alpha_model", "get_forex_alpha_model")
    def validate_carry_trade(self): return self._factory_check("modules.forex.forex_carry_trade_engine", "get_forex_carry_trade_engine")
    def validate_central_bank(self): return self._factory_check("modules.forex.forex_central_bank_engine", "get_forex_central_bank_engine")
    def validate_sentiment(self): return self._factory_check("modules.forex.forex_sentiment_engine", "get_forex_sentiment_engine")
    def validate_macro_regime(self): return self._factory_check("modules.forex.forex_macro_regime_engine", "get_forex_macro_regime_engine")
    def validate_institutional_scanner(self): return self._factory_check("modules.forex.forex_institutional_scanner", "get_forex_institutional_scanner")
    def validate_command_center(self): return self._factory_check("modules.forex.forex_command_center_engine", "get_forex_command_center_engine")

    # Execution
    def validate_portfolio_manager(self): return self._factory_check("modules.forex.forex_portfolio_manager", "get_forex_portfolio_manager")
    def validate_trade_execution(self): return self._factory_check("modules.forex.forex_trade_execution_engine", "get_forex_trade_execution_engine")
    def validate_order_management(self): return self._factory_check("modules.forex.forex_order_management_engine", "get_forex_order_management_engine")
    def validate_risk_management(self): return self._factory_check("modules.forex.forex_risk_management_engine", "get_forex_risk_management_engine")
    def validate_performance(self): return self._factory_check("modules.forex.forex_performance_analytics_engine", "get_forex_performance_analytics_engine")
    def validate_trade_journal(self): return self._factory_check("modules.forex.forex_trade_journal_engine", "get_forex_trade_journal_engine")
    def validate_strategy_engine(self): return self._factory_check("modules.forex.forex_strategy_engine", "get_forex_strategy_engine")
    def validate_strategy_lab(self): return self._factory_check("modules.forex.forex_strategy_lab", "get_forex_strategy_lab")
    def validate_portfolio_optimizer(self): return self._factory_check("modules.forex.forex_portfolio_optimizer", "get_forex_portfolio_optimizer")
    def validate_autonomous_trader(self): return self._factory_check("modules.forex.forex_autonomous_trader", "get_forex_autonomous_trader")

    # Platform
    def validate_ai_assistant(self): return self._factory_check("modules.forex.forex_ai_assistant", "get_forex_ai_assistant")
    def validate_ai_orchestrator(self): return self._factory_check("modules.forex.forex_ai_orchestrator", "get_forex_ai_orchestrator")
    def validate_command_processor(self): return self._factory_check("modules.forex.forex_command_processor", "get_forex_command_processor")
    def validate_control_plane(self): return self._factory_check("modules.forex.forex_control_plane", "get_forex_control_plane")
    def validate_operations_center(self): return self._factory_check("modules.forex.forex_operations_center", "get_forex_operations_center")
    def validate_supervisor(self): return self._factory_check("modules.forex.forex_supervisor", "get_forex_supervisor")
    def validate_master_controller(self): return self._factory_check("modules.forex.forex_master_controller", "get_forex_master_controller")
    def validate_enterprise_workspace(self): return self._factory_check("modules.forex.forex_enterprise_workspace", "get_forex_enterprise_workspace")
    def validate_institutional_workspace(self): return self._factory_check("modules.forex.forex_institutional_workspace", "get_forex_institutional_workspace")
    def validate_execution_center(self): return self._factory_check("modules.forex.forex_execution_center", "get_forex_execution_center")
    def validate_trading_desk(self): return self._factory_check("modules.forex.forex_trading_desk", "get_forex_trading_desk")
    def validate_institutional_terminal(self): return self._factory_check("modules.forex.forex_institutional_terminal", "get_forex_institutional_terminal")
    def validate_terminal_api(self): return self._factory_check("modules.forex.forex_terminal_api", "get_forex_terminal_api")
    def validate_terminal_dashboard_service(self): return self._factory_check("modules.forex.forex_terminal_dashboard_service", "get_forex_terminal_dashboard_service")
    def validate_terminal_controller(self): return self._factory_check("modules.forex.forex_terminal_controller", "get_forex_terminal_controller")
    def validate_terminal_router(self): return self._factory_check("modules.forex.forex_terminal_router", "get_forex_terminal_router")
    def validate_terminal_bridge(self): return self._factory_check("modules.forex.forex_terminal_bridge", "get_forex_terminal_bridge")
    def validate_streamlit_adapter(self): return self._factory_check("modules.forex.forex_streamlit_adapter", "get_forex_streamlit_adapter")
    def validate_app_adapter(self): return self._factory_check("modules.forex.forex_app_adapter", "get_forex_app_adapter")
    def validate_ui_integration(self): return self._factory_check("modules.forex.forex_ui_integration", "get_forex_ui_integration")
    def validate_application(self): return self._factory_check("modules.forex.forex_application", "get_forex_application")
    def validate_bootstrap(self): return self._factory_check("modules.forex.forex_bootstrap", "get_forex_bootstrap")
    def validate_app_router(self): return self._factory_check("modules.forex.forex_app_router", "get_forex_app_router")
    def validate_forex_module(self): return self._factory_check("modules.forex.forex_module", "get_forex_module")

    # Dashboards
    def validate_terminal_dashboard(self): return self._factory_check("modules.forex.forex_terminal_dashboard", "get_forex_terminal_dashboard")
    def validate_trading_desk_dashboard(self): return self._factory_check("modules.forex.forex_trading_desk_dashboard", "get_forex_trading_desk_dashboard")
    def validate_execution_dashboard(self): return self._factory_check("modules.forex.forex_execution_dashboard", "get_forex_execution_dashboard")
    def validate_portfolio_dashboard(self): return self._factory_check("modules.forex.forex_portfolio_dashboard", "get_forex_portfolio_dashboard")
    def validate_order_dashboard(self): return self._factory_check("modules.forex.forex_order_dashboard", "get_forex_order_dashboard")
    def validate_ai_dashboard(self): return self._factory_check("modules.forex.forex_ai_dashboard", "get_forex_ai_dashboard")
    def validate_workspace(self): return self._factory_check("modules.forex.forex_workspace", "get_forex_workspace")

    def report(self) -> Dict[str, Any]:
        rows = [r.to_dict() for r in self.results]
        passed = len([r for r in self.results if r.passed])
        failed = len(self.results) - passed

        by_category: Dict[str, Dict[str, int]] = {}
        for r in self.results:
            cat = by_category.setdefault(r.category, {"passed": 0, "failed": 0, "total": 0})
            cat["total"] += 1
            if r.passed:
                cat["passed"] += 1
            else:
                cat["failed"] += 1

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "READY_FOR_PRODUCTION" if failed == 0 else "NEEDS_ATTENTION",
            "total_tests": len(self.results),
            "passed": passed,
            "failed": failed,
            "by_category": by_category,
            "results": rows,
            "text_report": self.text_report(),
        }

    def text_report(self) -> str:
        passed = len([r for r in self.results if r.passed])
        failed = len(self.results) - passed

        lines = [
            "===========================================",
            "FOREX SYSTEM VALIDATION REPORT",
            "===========================================",
            "",
        ]

        categories = []
        for r in self.results:
            if r.category not in categories:
                categories.append(r.category)

        for category in categories:
            lines.append(category)
            lines.append("-------------------------------------------")
            for r in [x for x in self.results if x.category == category]:
                mark = "✓" if r.passed else "✗"
                lines.append(f"{mark} {r.name} — {r.status}")
                if not r.passed:
                    lines.append(f"  {r.message}")
            lines.append("")

        lines.extend([
            f"TOTAL TESTS : {len(self.results)}",
            f"PASSED      : {passed}",
            f"FAILED      : {failed}",
            "",
            "SYSTEM STATUS:",
            "READY FOR PRODUCTION" if failed == 0 else "NEEDS ATTENTION",
        ])

        return "\n".join(lines)


def run_forex_system_validation_suite(
    db=None,
    run_live_provider_checks: bool = False,
) -> Dict[str, Any]:
    return ForexSystemValidationSuite(
        db=db,
        run_live_provider_checks=run_live_provider_checks,
    ).run_all()


def render_forex_system_validation_suite(db=None):
    report = run_forex_system_validation_suite(db=db)

    try:
        import streamlit as st
        import pandas as pd
    except Exception:
        return report

    st.title("Forex System Validation Suite")

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Tests", report["total_tests"])
    c2.metric("Passed", report["passed"])
    c3.metric("Failed", report["failed"])

    if report["failed"] == 0:
        st.success("Forex subsystem is ready for production validation.")
    else:
        st.warning("Forex subsystem has failed checks that need review.")

    st.code(report["text_report"])

    try:
        st.dataframe(pd.DataFrame(report["results"]), use_container_width=True, hide_index=True)
    except Exception:
        st.json(report["results"])

    return report
