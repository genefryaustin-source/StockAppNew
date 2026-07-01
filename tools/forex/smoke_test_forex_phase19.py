from __future__ import annotations

import importlib
import traceback

MODULES = [
    "modules.forex.forex_decision_engine",
    "modules.forex.forex_trade_scoring_engine",
    "modules.forex.forex_conviction_engine",
    "modules.forex.forex_trade_priority_engine",
    "modules.forex.forex_risk_committee",
    "modules.forex.forex_trade_gatekeeper",
    "modules.forex.forex_portfolio_constraints",
    "modules.forex.forex_position_limit_engine",
    "modules.forex.forex_opportunity_scanner",
    "modules.forex.forex_breakout_scanner",
    "modules.forex.forex_reversal_scanner",
    "modules.forex.forex_mean_reversion_scanner",
    "modules.forex.forex_trend_scanner",
    "modules.forex.forex_ai_deal_room",
    "modules.forex.forex_trade_review_engine",
    "modules.forex.forex_trade_vote_engine",
    "modules.forex.forex_real_time_monitor",
    "modules.forex.forex_position_monitor",
    "modules.forex.forex_risk_monitor_v2",
    "modules.forex.forex_trade_monitor",
    "modules.forex.forex_executive_command_center",
]


def main() -> int:
    failed = 0
    print("Forex Phase 19 smoke test")
    for module in MODULES:
        try:
            importlib.import_module(module)
            print("PASS", module)
        except Exception:
            failed += 1
            print("FAIL", module)
            traceback.print_exc()

    if failed:
        return 1

    try:
        from modules.forex.forex_executive_command_center import get_forex_executive_command_center
        payload = get_forex_executive_command_center().dashboard(snapshot={})
        required = [
            "executive_summary", "decision_engine", "opportunity_scanner",
            "risk_committee", "ai_deal_room", "trade_queue",
            "portfolio_constraints", "real_time_monitor", "execution_readiness",
        ]
        missing = [key for key in required if key not in payload]
        if missing:
            print("FAIL missing payload keys", missing)
            return 1
        print("PASS executive command center payload")
    except Exception:
        traceback.print_exc()
        return 1

    print("PASSED: Phase 19 smoke test complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
