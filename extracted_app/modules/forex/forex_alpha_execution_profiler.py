"""
===============================================================================
Sprint 25 - Phase 1
Forex Alpha Execution Profiler

File:
    modules/forex/forex_alpha_execution_profiler.py

Purpose:
    Centralized execution profiler for the Forex Alpha Engine.

This module is intentionally dependency-light so it can be imported from any
Forex module without creating circular imports.

Author:
    StockApp Sprint 25
===============================================================================
"""

from __future__ import annotations

import inspect
import threading
import time
import traceback
import uuid

from collections import defaultdict
from contextlib import ContextDecorator
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable, Dict, List, Optional


# =============================================================================
# Helpers
# =============================================================================

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# =============================================================================
# Models
# =============================================================================

@dataclass
class AlphaExecutionRecord:

    execution_id: str

    cycle_id: str

    function: str

    caller: str

    caller_file: str

    caller_line: int

    thread_name: str

    thread_id: int

    started_at: str

    completed_at: Optional[str] = None

    elapsed_ms: float = 0.0

    success: bool = True

    exception: Optional[str] = None

    metadata: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Profiler
# =============================================================================

class ForexAlphaExecutionProfiler:

    def __init__(self):

        self.enabled = True

        self._records: List[AlphaExecutionRecord] = []

        self._lock = threading.RLock()

        self._cycle_id = str(uuid.uuid4())

        self._function_counts = defaultdict(int)

        self._caller_counts = defaultdict(int)

        self._function_elapsed = defaultdict(float)

        self._call_graph = defaultdict(list)

    # ------------------------------------------------------------------

    def enable(self):

        self.enabled = True

    def disable(self):

        self.enabled = False

    # ------------------------------------------------------------------

    def reset(self):

        with self._lock:

            self._records.clear()

            self._function_counts.clear()

            self._caller_counts.clear()

            self._function_elapsed.clear()

            self._call_graph.clear()

            self._cycle_id = str(uuid.uuid4())

    # ------------------------------------------------------------------

    def new_cycle(self):

        with self._lock:

            self._cycle_id = str(uuid.uuid4())

    # ------------------------------------------------------------------

    @property
    def cycle_id(self):

        return self._cycle_id

    # ------------------------------------------------------------------

    def _caller(self):

        stack = inspect.stack()

        if len(stack) < 4:

            return "-", "-", 0

        frame = stack[3]

        return (

            frame.function,

            frame.filename,

            frame.lineno,

        )

    # ------------------------------------------------------------------

    def start(

        self,

        function_name: str,

        metadata: Optional[Dict[str, Any]] = None,

    ) -> AlphaExecutionRecord:

        caller, file_name, line = self._caller()

        record = AlphaExecutionRecord(

            execution_id=str(uuid.uuid4()),

            cycle_id=self._cycle_id,

            function=function_name,

            caller=caller,

            caller_file=file_name,

            caller_line=line,

            thread_name=threading.current_thread().name,

            thread_id=threading.get_ident(),

            started_at=_utc_now(),

            metadata=metadata or {},

        )

        record._started_perf = time.perf_counter()

        return record

    # ------------------------------------------------------------------

    def finish(

        self,

        record: AlphaExecutionRecord,

        success: bool = True,

        exception: Optional[Exception] = None,

    ):

        record.completed_at = _utc_now()

        record.elapsed_ms = (

            time.perf_counter() -

            record._started_perf

        ) * 1000.0

        record.success = success

        if exception:

            record.exception = str(exception)

        with self._lock:

            self._records.append(record)

            self._function_counts[record.function] += 1

            self._caller_counts[record.caller] += 1

            self._function_elapsed[record.function] += record.elapsed_ms

            self._call_graph[record.caller].append(record.function)

    # ------------------------------------------------------------------

    def profile(

        self,

        function_name: Optional[str] = None,

        metadata: Optional[Dict[str, Any]] = None,

    ):

        profiler = self

        class _Profiler(ContextDecorator):

            def __enter__(self):

                self.record = profiler.start(

                    function_name=function_name or "Unknown",

                    metadata=metadata,

                )

                return self

            def __exit__(self, exc_type, exc, tb):

                profiler.finish(

                    self.record,

                    success=exc is None,

                    exception=exc,

                )

                return False

        return _Profiler()

    # ------------------------------------------------------------------

    def profile_function(

        self,

        function_name: Optional[str] = None,

    ):

        def decorator(func):

            @wraps(func)

            def wrapper(*args, **kwargs):

                if not self.enabled:

                    return func(*args, **kwargs)

                record = self.start(

                    function_name or func.__qualname__,

                )

                try:

                    result = func(*args, **kwargs)

                    self.finish(record)

                    return result

                except Exception as exc:

                    self.finish(

                        record,

                        success=False,

                        exception=exc,

                    )

                    raise

            return wrapper

        return decorator

    # ------------------------------------------------------------------

    def records(self):

        with self._lock:

            return list(self._records)

    # ------------------------------------------------------------------

    def execution_summary(self):

        with self._lock:

            rows = []

            for function in sorted(self._function_counts):

                count = self._function_counts[function]

                total = self._function_elapsed[function]

                rows.append(

                    {

                        "function": function,

                        "executions": count,

                        "total_ms": round(total, 2),

                        "average_ms": round(

                            total / max(count, 1),

                            2,

                        ),

                    }

                )

            return rows

    # ------------------------------------------------------------------

    def duplicate_executions(self):

        return [

            row

            for row in self.execution_summary()

            if row["executions"] > 1

        ]

    # ------------------------------------------------------------------

    def caller_summary(self):

        with self._lock:

            return [

                {

                    "caller": caller,

                    "executions": count,

                }

                for caller, count

                in sorted(

                    self._caller_counts.items(),

                    key=lambda x: x[1],

                    reverse=True,

                )

            ]

    # ------------------------------------------------------------------

    def call_graph(self):

        with self._lock:

            return {

                k: sorted(set(v))

                for k, v

                in self._call_graph.items()

            }

    # ------------------------------------------------------------------

    def slowest(

        self,

        limit: int = 25,

    ):

        rows = sorted(

            self.records(),

            key=lambda x: x.elapsed_ms,

            reverse=True,

        )

        return [

            asdict(r)

            for r in rows[:limit]

        ]

    # ------------------------------------------------------------------

    def metrics(self):

        with self._lock:

            elapsed = sum(

                r.elapsed_ms

                for r in self._records

            )

            failures = len(

                [

                    r

                    for r in self._records

                    if not r.success

                ]

            )

            return {

                "cycle_id": self._cycle_id,

                "executions": len(self._records),

                "unique_functions": len(self._function_counts),

                "unique_callers": len(self._caller_counts),

                "duplicates": len(self.duplicate_executions()),

                "failures": failures,

                "elapsed_ms": round(elapsed, 2),

            }

    # ------------------------------------------------------------------

    def export(self):

        return {

            "metrics": self.metrics(),

            "summary": self.execution_summary(),

            "duplicates": self.duplicate_executions(),

            "callers": self.caller_summary(),

            "call_graph": self.call_graph(),

            "slowest": self.slowest(),

            "records": [

                asdict(r)

                for r in self.records()

            ],

        }


# =============================================================================
# Singleton
# =============================================================================

_PROFILER: Optional[ForexAlphaExecutionProfiler] = None


def get_forex_alpha_execution_profiler():

    global _PROFILER

    if _PROFILER is None:

        _PROFILER = ForexAlphaExecutionProfiler()

    return _PROFILER


# =============================================================================
# Public Decorator
# =============================================================================

def profile_alpha_execution(

    function_name: Optional[str] = None,

):

    return get_forex_alpha_execution_profiler().profile_function(

        function_name=function_name,

    )


# =============================================================================
# Convenience API
# =============================================================================

def alpha_execution_metrics():

    return get_forex_alpha_execution_profiler().metrics()


def alpha_execution_summary():

    return get_forex_alpha_execution_profiler().execution_summary()


def alpha_duplicate_report():

    return get_forex_alpha_execution_profiler().duplicate_executions()


def alpha_call_graph():

    return get_forex_alpha_execution_profiler().call_graph()


def reset_alpha_execution_profiler():

    get_forex_alpha_execution_profiler().reset()

    def start_phase(self, phase_name: str):

        import time

        self._phase_start[phase_name] = time.perf_counter()

    def end_phase(self, phase_name: str):

        import time

        started = self._phase_start.pop(phase_name, None)

        if started is None:
            return

        elapsed = (time.perf_counter() - started) * 1000.0

        self._phase_timings.setdefault(phase_name, []).append(elapsed)

        print(f"[ALPHA] {phase_name}: {elapsed:.2f} ms")

    def phase_summary(self):

        summary = {}

        for phase, values in self._phase_timings.items():
            summary[phase] = {
                "count": len(values),
                "total_ms": round(sum(values), 2),
                "average_ms": round(sum(values) / len(values), 2),
                "max_ms": round(max(values), 2),
            }

        return summary