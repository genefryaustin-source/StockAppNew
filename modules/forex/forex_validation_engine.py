from __future__ import annotations

import importlib
import json
import time
import traceback
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple


PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"
SKIP = "SKIP"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _json_safe(value: Any) -> Any:
    try:
        json.dumps(value, default=str)
        return value
    except Exception:
        return str(value)


@dataclass
class ForexValidationResult:
    name: str
    status: str
    message: str = ""
    duration_ms: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)
    started_at: str = ""
    finished_at: str = ""
    error: Optional[str] = None

    @property
    def passed(self) -> bool:
        return self.status == PASS

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["details"] = _json_safe(data.get("details", {}))
        return data


@dataclass
class ForexValidationReport:
    name: str
    status: str
    score: float
    passed: int
    failed: int
    warned: int
    skipped: int
    total: int
    duration_ms: float
    started_at: str
    finished_at: str
    results: List[Dict[str, Any]]
    summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ForexValidationEngine:
    """Core validation runner for the Forex operations/runtime subsystem."""

    def __init__(self, db: Any = None, user: Any = None, tenant_id: str = "default") -> None:
        self.db = db
        self.user = user
        self.tenant_id = tenant_id or "default"

    def _run_check(self, name: str, fn: Callable[[], ForexValidationResult | Dict[str, Any] | bool | None]) -> ForexValidationResult:
        started = utc_now_iso()
        t0 = time.perf_counter()
        try:
            raw = fn()
            duration_ms = round((time.perf_counter() - t0) * 1000, 3)
            finished = utc_now_iso()

            if isinstance(raw, ForexValidationResult):
                raw.duration_ms = raw.duration_ms or duration_ms
                raw.started_at = raw.started_at or started
                raw.finished_at = raw.finished_at or finished
                return raw

            if isinstance(raw, dict):
                status = str(raw.get("status", PASS)).upper()
                if status in {"OK", "SUCCESS", "SUCCEEDED"}:
                    status = PASS
                elif status in {"ERROR", "FAILED"}:
                    status = FAIL
                elif status not in {PASS, FAIL, WARN, SKIP}:
                    status = PASS if raw.get("passed", True) else FAIL
                return ForexValidationResult(
                    name=name,
                    status=status,
                    message=str(raw.get("message", "")),
                    duration_ms=duration_ms,
                    details={k: v for k, v in raw.items() if k not in {"status", "message"}},
                    started_at=started,
                    finished_at=finished,
                    error=raw.get("error"),
                )

            if raw is False:
                return ForexValidationResult(name=name, status=FAIL, message="Check returned False.", duration_ms=duration_ms, started_at=started, finished_at=finished)

            return ForexValidationResult(name=name, status=PASS, message="Check completed.", duration_ms=duration_ms, started_at=started, finished_at=finished)

        except Exception as exc:
            duration_ms = round((time.perf_counter() - t0) * 1000, 3)
            return ForexValidationResult(
                name=name,
                status=FAIL,
                message=str(exc),
                duration_ms=duration_ms,
                details={"traceback": traceback.format_exc()},
                started_at=started,
                finished_at=utc_now_iso(),
                error=exc.__class__.__name__,
            )

    def _import_object(self, module_path: str, object_name: str) -> Any:
        module = importlib.import_module(module_path)
        return getattr(module, object_name)

    def check_import(self, module_path: str, object_name: Optional[str] = None) -> ForexValidationResult:
        label = f"Import {module_path}" if object_name is None else f"Import {module_path}.{object_name}"

        def _check() -> Dict[str, Any]:
            module = importlib.import_module(module_path)
            if object_name:
                obj = getattr(module, object_name)
                return {"status": PASS, "message": "Import resolved.", "object": str(obj)}
            return {"status": PASS, "message": "Module import resolved."}

        return self._run_check(label, _check)

    def check_scheduler(self, pairs: Optional[List[str]] = None) -> ForexValidationResult:
        pairs = pairs or ["EUR/USD", "GBP/USD"]

        def _check() -> Dict[str, Any]:
            Scheduler = self._import_object("modules.forex.forex_scheduler", "ForexScheduler")
            scheduler = Scheduler()
            created = scheduler.schedule_cycle(pairs=pairs, enqueue=True)
            count = len(created) if hasattr(created, "__len__") else 0
            if count <= 0:
                return {"status": FAIL, "message": "Scheduler did not create jobs.", "created": created}
            return {"status": PASS, "message": f"Scheduler created {count} jobs.", "created_count": count, "sample": list(created)[:5] if isinstance(created, list) else created}

        return self._run_check("Scheduler", _check)

    def check_operations_snapshot(self) -> ForexValidationResult:
        def _check() -> Dict[str, Any]:
            Center = self._import_object("modules.forex.forex_operations_center", "ForexOperationsCenter")
            center = Center()
            snap = center.snapshot()
            if not isinstance(snap, dict):
                return {"status": FAIL, "message": "Snapshot did not return a dict.", "snapshot": snap}
            if "summary" not in snap:
                return {"status": FAIL, "message": "Snapshot missing summary.", "snapshot": snap}
            return {"status": PASS, "message": "Operations snapshot available.", "summary": snap.get("summary", {}), "job_count": len(snap.get("jobs", []) or []), "event_count": len(snap.get("events", []) or [])}

        return self._run_check("Operations Snapshot", _check)

    def check_runtime_tick(self, max_jobs: int = 5) -> ForexValidationResult:
        def _check() -> Dict[str, Any]:
            Runtime = self._import_object("modules.forex.forex_runtime_controller", "ForexRuntimeController")
            runtime = Runtime()
            result = runtime.tick(max_jobs=max_jobs)
            if not isinstance(result, dict):
                return {"status": WARN, "message": "Runtime tick completed but returned non-dict result.", "result": result}
            return {"status": PASS, "message": "Runtime tick executed.", "result": result}

        return self._run_check("Runtime Tick", _check)

    def check_optimizer(self) -> ForexValidationResult:
        def _check() -> Dict[str, Any]:
            Optimizer = self._import_object("modules.forex.forex_autonomous_optimizer", "ForexAutonomousOptimizer")
            optimizer = Optimizer()
            result = optimizer.optimize()
            return {"status": PASS, "message": "Optimizer executed.", "result": result}

        return self._run_check("Optimizer", _check)

    def check_governor(self) -> ForexValidationResult:
        def _check() -> Dict[str, Any]:
            Governor = self._import_object("modules.forex.forex_resource_governor", "ForexResourceGovernor")
            governor = Governor()
            for method in ("snapshot", "status", "govern", "evaluate"):
                if hasattr(governor, method):
                    return {"status": PASS, "message": f"Governor method {method} executed.", "result": getattr(governor, method)()}
            return {"status": WARN, "message": "Governor imported but no known status method was found.", "object": str(governor)}

        return self._run_check("Resource Governor", _check)

    def run_checks(self, checks: Iterable[Tuple[str, Callable[[], ForexValidationResult | Dict[str, Any] | bool | None]]], name: str = "Forex Validation") -> ForexValidationReport:
        started = utc_now_iso()
        t0 = time.perf_counter()
        results: List[ForexValidationResult] = []
        for check_name, check_fn in checks:
            results.append(self._run_check(check_name, check_fn))
        duration_ms = round((time.perf_counter() - t0) * 1000, 3)
        finished = utc_now_iso()
        passed = sum(1 for r in results if r.status == PASS)
        failed = sum(1 for r in results if r.status == FAIL)
        warned = sum(1 for r in results if r.status == WARN)
        skipped = sum(1 for r in results if r.status == SKIP)
        total = len(results)
        score = round((passed / total) * 100, 2) if total else 0.0
        status = PASS if failed == 0 else FAIL
        if failed == 0 and warned > 0:
            status = WARN
        return ForexValidationReport(
            name=name,
            status=status,
            score=score,
            passed=passed,
            failed=failed,
            warned=warned,
            skipped=skipped,
            total=total,
            duration_ms=duration_ms,
            started_at=started,
            finished_at=finished,
            results=[r.to_dict() for r in results],
            summary={"tenant_id": self.tenant_id},
        )

    def run_core_validation(self) -> Dict[str, Any]:
        checks = [
            ("Import Operations Center", lambda: self.check_import("modules.forex.forex_operations_center", "ForexOperationsCenter")),
            ("Import Scheduler", lambda: self.check_import("modules.forex.forex_scheduler", "ForexScheduler")),
            ("Import Runtime Controller", lambda: self.check_import("modules.forex.forex_runtime_controller", "ForexRuntimeController")),
            ("Import Job Registry", lambda: self.check_import("modules.forex.forex_job_registry", "ForexJobRegistry")),
            ("Import Execution Queue", lambda: self.check_import("modules.forex.forex_execution_queue", "ForexExecutionQueue")),
            ("Operations Snapshot", self.check_operations_snapshot),
            ("Scheduler", self.check_scheduler),
            ("Runtime Tick", self.check_runtime_tick),
            ("Optimizer", self.check_optimizer),
        ]
        return self.run_checks(checks, name="Forex Core Validation").to_dict()
