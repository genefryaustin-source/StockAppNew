from __future__ import annotations

from typing import Any, Dict, List, Optional

from modules.forex.forex_validation_engine import FAIL, PASS, ForexValidationEngine


class ForexIntegrationTestSuite:
    """End-to-end Forex integration tests: schedule -> queue -> runtime -> snapshot."""

    def __init__(self, db: Any = None, user: Any = None) -> None:
        self.db = db
        self.user = user
        self.engine = ForexValidationEngine(db=db, user=user)

    def run_schedule_runtime_flow(self, pairs: Optional[List[str]] = None, max_jobs: int = 10) -> Dict[str, Any]:
        pairs = pairs or ["EUR/USD", "GBP/USD", "USD/JPY"]
        details: Dict[str, Any] = {"pairs": pairs, "max_jobs": max_jobs}

        scheduler_result = self.engine.check_scheduler(pairs=pairs).to_dict()
        details["scheduler"] = scheduler_result
        if scheduler_result.get("status") == FAIL:
            return {"status": FAIL, "message": "Scheduler failed; integration flow stopped.", **details}

        before = self.engine.check_operations_snapshot().to_dict()
        details["before_snapshot"] = before

        runtime = self.engine.check_runtime_tick(max_jobs=max_jobs).to_dict()
        details["runtime"] = runtime
        if runtime.get("status") == FAIL:
            return {"status": FAIL, "message": "Runtime tick failed.", **details}

        after = self.engine.check_operations_snapshot().to_dict()
        details["after_snapshot"] = after
        return {"status": PASS, "message": "Schedule/runtime integration flow completed.", **details}

    def run_queue_drain_flow(self, pairs: Optional[List[str]] = None, tick_size: int = 10, max_ticks: int = 10) -> Dict[str, Any]:
        pairs = pairs or ["EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF", "AUD/USD"]
        schedule = self.engine.check_scheduler(pairs=pairs).to_dict()
        ticks: List[Dict[str, Any]] = []
        for _ in range(max_ticks):
            snap_result = self.engine.check_operations_snapshot().to_dict()
            summary = ((snap_result.get("details") or {}).get("summary") or {})
            open_jobs = int(summary.get("open_jobs", 0) or 0)
            if open_jobs <= 0:
                break
            tick = self.engine.check_runtime_tick(max_jobs=tick_size).to_dict()
            ticks.append(tick)
            if tick.get("status") == FAIL:
                break
        final_snap = self.engine.check_operations_snapshot().to_dict()
        final_summary = ((final_snap.get("details") or {}).get("summary") or {})
        failed_jobs = int(final_summary.get("failed_jobs", 0) or 0)
        status = FAIL if failed_jobs > 0 else PASS
        return {
            "status": status,
            "message": "Queue drain flow completed." if status == PASS else "Queue drain completed with failed jobs.",
            "schedule": schedule,
            "ticks": ticks,
            "final_snapshot": final_snap,
            "final_summary": final_summary,
        }

    def run_all(self) -> Dict[str, Any]:
        checks = [
            ("Schedule Runtime Flow", self.run_schedule_runtime_flow),
            ("Queue Drain Flow", self.run_queue_drain_flow),
        ]
        return self.engine.run_checks(checks, name="Forex Integration Test Suite").to_dict()
