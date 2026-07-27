"""
modules/forex/forex_enterprise_platform.py

Master enterprise facade for the Forex subsystem.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

try:
    from modules.forex.forex_lifecycle_manager import get_forex_lifecycle_manager
except Exception:
    get_forex_lifecycle_manager = None

try:
    from modules.forex.forex_operations_control_center import get_forex_operations_control_center
except Exception:
    get_forex_operations_control_center = None

try:
    from modules.forex.forex_deployment_orchestrator import get_forex_deployment_orchestrator
except Exception:
    get_forex_deployment_orchestrator = None

try:
    from modules.forex.forex_release_manager import get_forex_release_manager
except Exception:
    get_forex_release_manager = None

try:
    from modules.forex.forex_runtime_manager import get_forex_runtime_manager
except Exception:
    get_forex_runtime_manager = None

try:
    from modules.forex.forex_registry import get_forex_registry
except Exception:
    get_forex_registry = None

try:
    from modules.forex.forex_trading_desk import get_forex_trading_desk
except Exception:
    get_forex_trading_desk = None

try:
    from modules.forex.forex_institutional_terminal import get_forex_institutional_terminal
except Exception:
    get_forex_institutional_terminal = None

try:
    from modules.forex.forex_ai_assistant import get_forex_ai_assistant
except Exception:
    get_forex_ai_assistant = None

try:
    from modules.forex.forex_portfolio_manager import get_forex_portfolio_manager
except Exception:
    get_forex_portfolio_manager = None

try:
    from modules.forex.forex_trade_execution_engine import get_forex_trade_execution_engine
except Exception:
    get_forex_trade_execution_engine = None

try:
    from modules.forex.forex_strategy_lab import get_forex_strategy_lab
except Exception:
    get_forex_strategy_lab = None

try:
    from modules.forex.forex_production_readiness_suite import run_forex_production_readiness_suite
except Exception:
    run_forex_production_readiness_suite = None

try:
    from modules.forex.forex_system_validation_suite import run_forex_system_validation_suite
except Exception:
    run_forex_system_validation_suite = None

try:
    from modules.forex.forex_performance_benchmark_suite import run_forex_performance_benchmark_suite
except Exception:
    run_forex_performance_benchmark_suite = None

try:
    from modules.forex.forex_stress_test_suite import run_forex_stress_test_suite
except Exception:
    run_forex_stress_test_suite = None

try:
    from modules.forex.forex_chaos_test_suite import run_forex_chaos_test_suite
except Exception:
    run_forex_chaos_test_suite = None


class ForexEnterprisePlatform:
    """
    Canonical enterprise-level integration point for the full Forex platform.

    This object sits above:
    - lifecycle
    - runtime
    - deployment
    - registry
    - trading desk
    - terminal
    - AI
    - portfolio
    - execution
    - validation and operational suites
    """

    def __init__(self, db: Optional[Any] = None):
        self.db = db

        self.lifecycle = get_forex_lifecycle_manager(db=db) if get_forex_lifecycle_manager else None
        self.operations = get_forex_operations_control_center(db=db) if get_forex_operations_control_center else None
        self.deployment = get_forex_deployment_orchestrator(db=db) if get_forex_deployment_orchestrator else None
        self.release = get_forex_release_manager(db=db) if get_forex_release_manager else None
        self.runtime = get_forex_runtime_manager() if get_forex_runtime_manager else None
        self.registry = get_forex_registry() if get_forex_registry else None
        self.trading_desk = get_forex_trading_desk(db=db) if get_forex_trading_desk else None
        self.terminal = get_forex_institutional_terminal(db=db) if get_forex_institutional_terminal else None
        self.ai = get_forex_ai_assistant(db=db) if get_forex_ai_assistant else None
        self.portfolio = get_forex_portfolio_manager(db=db) if get_forex_portfolio_manager else None
        self.execution = get_forex_trade_execution_engine(db=db) if get_forex_trade_execution_engine else None
        self.strategy_lab = get_forex_strategy_lab(db=db) if get_forex_strategy_lab else None

    def startup(self) -> Dict[str, Any]:
        if self.lifecycle:
            return self.lifecycle.startup()
        if self.runtime:
            return self.runtime.start()
        return {"status": "UNAVAILABLE", "message": "Lifecycle/runtime manager unavailable."}

    def shutdown(self) -> Dict[str, Any]:
        if self.lifecycle:
            return self.lifecycle.shutdown()
        if self.runtime:
            return self.runtime.stop()
        return {"status": "UNAVAILABLE", "message": "Lifecycle/runtime manager unavailable."}

    def health(self) -> Dict[str, Any]:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "lifecycle": self.lifecycle.health() if self.lifecycle else {"status": "UNAVAILABLE"},
            "runtime": self.runtime.status() if self.runtime else {"status": "UNAVAILABLE"},
            "registry": self.registry.summary() if self.registry else {"status": "UNAVAILABLE"},
            "deployment": self.deployment.deployment_status() if self.deployment else {"status": "UNAVAILABLE"},
        }

    def status(self) -> Dict[str, Any]:
        return self.enterprise_snapshot(compact=True)

    def deploy_staging(self) -> Dict[str, Any]:
        if not self.deployment:
            return {"status": "UNAVAILABLE"}
        return self.deployment.deploy_staging()

    def deploy_production(self) -> Dict[str, Any]:
        if not self.deployment:
            return {"status": "UNAVAILABLE"}
        return self.deployment.deploy_production()

    def rollback(self, deployment_id: Optional[str] = None, reason: str = "") -> Dict[str, Any]:
        if not self.deployment:
            return {"status": "UNAVAILABLE"}
        return self.deployment.rollback(deployment_id=deployment_id, reason=reason)

    def validate(self) -> Dict[str, Any]:
        if run_forex_system_validation_suite is None:
            return {"status": "UNAVAILABLE"}
        return run_forex_system_validation_suite(db=self.db)

    def benchmark(self) -> Dict[str, Any]:
        if run_forex_performance_benchmark_suite is None:
            return {"status": "UNAVAILABLE"}
        return run_forex_performance_benchmark_suite()

    def stress_test(self) -> Dict[str, Any]:
        if run_forex_stress_test_suite is None:
            return {"status": "UNAVAILABLE"}
        return run_forex_stress_test_suite()

    def chaos_test(self) -> Dict[str, Any]:
        if run_forex_chaos_test_suite is None:
            return {"status": "UNAVAILABLE"}
        return run_forex_chaos_test_suite()

    def production_readiness(self) -> Dict[str, Any]:
        if run_forex_production_readiness_suite is None:
            return {"status": "UNAVAILABLE"}
        return run_forex_production_readiness_suite(db=self.db)

    def trading_snapshot(self, **kwargs) -> Dict[str, Any]:
        if not self.trading_desk:
            return {"status": "UNAVAILABLE"}
        return self.trading_desk.dashboard(**kwargs)

    def terminal_snapshot(self, **kwargs) -> Dict[str, Any]:
        if not self.terminal:
            return {"status": "UNAVAILABLE"}
        return self.terminal.snapshot(**kwargs)

    def ai_briefing(self) -> Dict[str, Any]:
        if not self.ai:
            return {"status": "UNAVAILABLE"}
        return self.ai.daily_briefing()

    def portfolio_summary(self, **kwargs) -> Dict[str, Any]:
        if not self.portfolio:
            return {"status": "UNAVAILABLE"}
        return self.portfolio.portfolio_summary(**kwargs)

    def execute_order(self, **kwargs) -> Dict[str, Any]:
        if not self.execution:
            return {"status": "UNAVAILABLE"}
        return self.execution.submit_order(**kwargs)

    def strategy_lab_snapshot(self) -> Dict[str, Any]:
        if not self.strategy_lab:
            return {"status": "UNAVAILABLE"}
        return self.strategy_lab.run()

    def enterprise_snapshot(self, compact: bool = False, **kwargs) -> Dict[str, Any]:
        snapshot = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "health": self.health() if not compact else {
                "runtime": self.runtime.status() if self.runtime else {"status": "UNAVAILABLE"},
                "registry": self.registry.summary() if self.registry else {"status": "UNAVAILABLE"},
            },
            "operations": self.operations.dashboard() if self.operations and not compact else {},
            "deployment": self.deployment.deployment_status() if self.deployment else {"status": "UNAVAILABLE"},
            "release_manifest": self.release.build_release_manifest() if self.release and not compact else {},
            "trading_desk": self.trading_snapshot(**kwargs) if self.trading_desk and not compact else {},
            "terminal": self.terminal_snapshot(**kwargs) if self.terminal and not compact else {},
            "ai": self.ai_briefing() if self.ai and not compact else {},
            "portfolio": self.portfolio_summary(**kwargs) if self.portfolio and not compact else {},
            "strategy_lab": self.strategy_lab_snapshot() if self.strategy_lab and not compact else {},
        }
        return snapshot

    def run_full_operational_check(self) -> Dict[str, Any]:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "health": self.health(),
            "validation": self.validate(),
            "benchmark": self.benchmark(),
            "stress_test": self.stress_test(),
            "chaos_test": self.chaos_test(),
            "production_readiness": self.production_readiness(),
        }


_PLATFORM = None


def get_forex_enterprise_platform(db: Optional[Any] = None) -> ForexEnterprisePlatform:
    global _PLATFORM
    if _PLATFORM is None or (db is not None and _PLATFORM.db is None):
        _PLATFORM = ForexEnterprisePlatform(db=db)
    return _PLATFORM
