from __future__ import annotations

PHASE19_REQUIRED_MODULES = [
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


def validate_phase19_decision_platform(db=None, snapshot=None):
    from importlib import import_module

    results = []
    artifacts = {}
    snapshot = snapshot or {}

    def add(test, passed, details=""):
        results.append({
            "Category": "Phase 19",
            "Test": test,
            "Passed": bool(passed),
            "Severity": "required",
            "Details": details,
        })

    for module in PHASE19_REQUIRED_MODULES:
        try:
            import_module(module)
            add(f"Import {module}", True, "import ok")
        except Exception as exc:
            add(f"Import {module}", False, str(exc))

    try:
        from modules.forex.forex_executive_command_center import get_forex_executive_command_center
        executive = get_forex_executive_command_center(db=db).dashboard(snapshot=snapshot)
        artifacts["phase19_executive_command_center"] = executive
        add("Executive command center payload", isinstance(executive, dict) and executive.get("status") == "READY", str(executive.get("status")))

        required = [
            "executive_summary",
            "decision_engine",
            "opportunity_scanner",
            "risk_committee",
            "ai_deal_room",
            "trade_queue",
            "portfolio_constraints",
            "real_time_monitor",
            "execution_readiness",
        ]
        for key in required:
            add(f"executive.{key}", key in executive, "present" if key in executive else "missing")

        add("Decision engine decisions", bool((executive.get("decision_engine") or {}).get("decisions")),
            f"{len((executive.get('decision_engine') or {}).get('decisions', []))} decisions")
        add("Opportunity scanner rows", bool((executive.get("opportunity_scanner") or {}).get("opportunities")),
            f"{len((executive.get('opportunity_scanner') or {}).get('opportunities', []))} opportunities")
        add("Risk committee reviews", "reviews" in (executive.get("risk_committee") or {}),
            f"{len((executive.get('risk_committee') or {}).get('reviews', []))} reviews")
        add("AI Deal Room reviews", "reviews" in (executive.get("ai_deal_room") or {}),
            f"{len((executive.get('ai_deal_room') or {}).get('reviews', []))} reviews")
    except Exception as exc:
        add("Executive command center validation", False, str(exc))

    return {
        "status": "PASS" if all(r["Passed"] for r in results if r["Severity"] == "required") else "FAIL",
        "results": results,
        "artifacts": artifacts,
    }
