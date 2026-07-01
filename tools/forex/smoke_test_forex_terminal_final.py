"""
Final Forex production smoke test.

Run from project root:

    python tools/forex/smoke_test_forex_terminal_final.py
"""

from __future__ import annotations

import importlib
import traceback


MODULES = [
    # Core / terminal
    "modules.forex.forex_portfolio_engine",
    "modules.forex.forex_terminal_api",
    "modules.forex.forex_terminal_dashboard",
    "modules.forex.forex_terminal_execution_service",
    "modules.forex.forex_terminal_validation_center",

    # Phase 5/6 workstation
    "modules.forex.forex_institutional_trade_ticket",
    "modules.forex.forex_ai_trade_assistant",
    "modules.forex.forex_institutional_risk_manager",
    "modules.forex.forex_autonomous_trading_engine",
    "modules.forex.forex_execution_monitor",
    "modules.forex.forex_institutional_workstation",
    "modules.forex.forex_trading_workspace",
    "modules.forex.forex_order_book",
    "modules.forex.forex_watchlist_manager",
    "modules.forex.forex_market_depth",
    "modules.forex.forex_trade_journal",
    "modules.forex.forex_execution_blotter",
    "modules.forex.forex_ai_command_center",
    "modules.forex.forex_economic_intelligence",
    "modules.forex.forex_microstructure_engine",
    "modules.forex.forex_autonomous_portfolio_manager",

    # Phase 11/12 production
    "modules.forex.forex_broker_base",
    "modules.forex.forex_broker_registry",
    "modules.forex.forex_broker_router",
    "modules.forex.forex_paper_broker",
    "modules.forex.forex_mt5_broker",
    "modules.forex.forex_oanda_broker",
    "modules.forex.forex_ibkr_broker",
    "modules.forex.forex_dxtrade_broker",
    "modules.forex.forex_institutional_risk_engine",
    "modules.forex.forex_portfolio_attribution",
    "modules.forex.forex_execution_analytics",
    "modules.forex.forex_ai_trade_supervisor",
    "modules.forex.forex_operations_health_monitor",
    "modules.forex.forex_phase12_production_services",
]


def main() -> int:
    failed = 0

    print("Forex terminal final production smoke test")
    print("=" * 60)

    for module in MODULES:
        try:
            importlib.import_module(module)
            print(f"PASS import {module}")
        except Exception:
            failed += 1
            print(f"FAIL import {module}")
            traceback.print_exc()

    print("=" * 60)
    if failed:
        print(f"FAILED: {failed} import(s) failed.")
        return 1

    print("PASSED: all imports succeeded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
