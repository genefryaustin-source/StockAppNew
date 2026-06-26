import importlib

MODULES = [
"modules.forex.forex_portfolio_engine",
"modules.forex.forex_terminal_api",
"modules.forex.forex_terminal_execution_service",
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
"modules.forex.forex_terminal_validation_center",
]

failed = 0
for m in MODULES:
    try:
        importlib.import_module(m)
        print("PASS", m)
    except Exception as e:
        failed += 1
        print("FAIL", m, e)
raise SystemExit(1 if failed else 0)
