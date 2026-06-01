"""
modules/analytics/sqlite_operation_profiler.py

SQLite Operation Profiler

Purpose
-------
Deep profiling tool for Analytics Fabric SQLite bottlenecks.

Used to identify where time is spent inside:

    register_job()
    enqueue_job()
    claim_jobs()
    complete_job()
    recover_expired_leases()

Measures:

    connection open time
    SQL execution time
    commit time
    close time

Also measures:

    query count
    commit count
    rollback count
    rows affected

Goal
----
Determine if bottlenecks are caused by:

    excessive connection creation
    excessive commits
    SQL inefficiency
    missing indexes
    transaction fragmentation
    SQLite locking

Usage
-----

from modules.analytics.sqlite_operation_profiler import (
    SQLiteOperationProfiler
)

profiler = SQLiteOperationProfiler()

with profiler.profile("register_job"):

    registry.register_job(...)

print(
    profiler.report()
)

"""

from __future__ import annotations

import sqlite3
import statistics
import threading
import time

from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# =============================================================================
# Helpers
# =============================================================================

def utc_now_iso() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


# =============================================================================
# Models
# =============================================================================

@dataclass
class SQLTiming:

    operation: str

    duration_ms: float

    timestamp: str = field(
        default_factory=utc_now_iso
    )


@dataclass
class SQLConnectionStats:

    opens: int = 0

    closes: int = 0

    commits: int = 0

    rollbacks: int = 0

    executes: int = 0

    executemany: int = 0

    total_open_time_ms: float = 0.0

    total_commit_time_ms: float = 0.0

    total_close_time_ms: float = 0.0

    total_execute_time_ms: float = 0.0


@dataclass
class SQLProfileResult:

    operation_name: str

    executions: int

    avg_ms: float

    min_ms: float

    max_ms: float

    p50_ms: float

    p95_ms: float

    p99_ms: float

    total_ms: float

    generated_at: str = field(
        default_factory=utc_now_iso
    )


# =============================================================================
# Main Profiler
# =============================================================================

class SQLiteOperationProfiler:

    """
    Generic SQLite profiler.

    Does not require modifications to
    analytics modules.

    Can wrap operations directly.
    """

    def __init__(self):

        self._lock = threading.Lock()

        self.operation_timings: Dict[
            str,
            List[float]
        ] = {}

        self.connection_stats = (
            SQLConnectionStats()
        )

    # =========================================================================
    # Operation Profiling
    # =========================================================================

    @contextmanager
    def profile(
        self,
        operation_name: str,
    ):

        start = (
            time.perf_counter()
        )

        try:

            yield

        finally:

            duration_ms = (
                (
                    time.perf_counter()
                    - start
                )
                * 1000
            )

            with self._lock:

                self.operation_timings\
                    .setdefault(
                        operation_name,
                        []
                    )\
                    .append(
                        duration_ms
                    )

    # =========================================================================
    # Connection Tracking
    # =========================================================================

    def record_connection_open(
        self,
        duration_ms: float,
    ):

        self.connection_stats.opens += 1

        self.connection_stats\
            .total_open_time_ms += (
                duration_ms
            )

    def record_connection_close(
        self,
        duration_ms: float,
    ):

        self.connection_stats.closes += 1

        self.connection_stats\
            .total_close_time_ms += (
                duration_ms
            )

    def record_commit(
        self,
        duration_ms: float,
    ):

        self.connection_stats.commits += 1

        self.connection_stats\
            .total_commit_time_ms += (
                duration_ms
            )

    def record_rollback(
        self,
    ):

        self.connection_stats\
            .rollbacks += 1

    def record_execute(
        self,
        duration_ms: float,
    ):

        self.connection_stats\
            .executes += 1

        self.connection_stats\
            .total_execute_time_ms += (
                duration_ms
            )

    def record_executemany(
        self,
        duration_ms: float,
    ):

        self.connection_stats\
            .executemany += 1

        self.connection_stats\
            .total_execute_time_ms += (
                duration_ms
            )

    # =========================================================================
    # Reports
    # =========================================================================

    def build_profile(
        self,
        operation_name: str,
    ) -> Optional[
        SQLProfileResult
    ]:

        timings = (
            self.operation_timings
            .get(
                operation_name,
                []
            )
        )

        if not timings:
            return None

        timings = sorted(
            timings
        )

        count = len(
            timings
        )

        return SQLProfileResult(
            operation_name=
                operation_name,

            executions=count,

            avg_ms=
                round(
                    statistics.mean(
                        timings
                    ),
                    4,
                ),

            min_ms=
                round(
                    min(
                        timings
                    ),
                    4,
                ),

            max_ms=
                round(
                    max(
                        timings
                    ),
                    4,
                ),

            p50_ms=
                round(
                    timings[
                        int(
                            count
                            * 0.50
                        )
                    ],
                    4,
                ),

            p95_ms=
                round(
                    timings[
                        min(
                            count - 1,
                            int(
                                count
                                * 0.95
                            ),
                        )
                    ],
                    4,
                ),

            p99_ms=
                round(
                    timings[
                        min(
                            count - 1,
                            int(
                                count
                                * 0.99
                            ),
                        )
                    ],
                    4,
                ),

            total_ms=
                round(
                    sum(
                        timings
                    ),
                    4,
                ),
        )

    def report(
        self,
    ) -> Dict[str, Any]:

        operations = {}

        for name in sorted(
            self.operation_timings
        ):

            profile = (
                self.build_profile(
                    name
                )
            )

            if profile:

                operations[
                    name
                ] = {
                    "executions":
                        profile.executions,

                    "avg_ms":
                        profile.avg_ms,

                    "min_ms":
                        profile.min_ms,

                    "max_ms":
                        profile.max_ms,

                    "p50_ms":
                        profile.p50_ms,

                    "p95_ms":
                        profile.p95_ms,

                    "p99_ms":
                        profile.p99_ms,

                    "total_ms":
                        profile.total_ms,
                }

        stats = (
            self.connection_stats
        )

        return {
            "operations":
                operations,

            "sqlite": {

                "opens":
                    stats.opens,

                "closes":
                    stats.closes,

                "commits":
                    stats.commits,

                "rollbacks":
                    stats.rollbacks,

                "executes":
                    stats.executes,

                "executemany":
                    stats.executemany,

                "total_open_time_ms":
                    round(
                        stats
                        .total_open_time_ms,
                        4,
                    ),

                "total_commit_time_ms":
                    round(
                        stats
                        .total_commit_time_ms,
                        4,
                    ),

                "total_close_time_ms":
                    round(
                        stats
                        .total_close_time_ms,
                        4,
                    ),

                "total_execute_time_ms":
                    round(
                        stats
                        .total_execute_time_ms,
                        4,
                    ),
            },
        }

    # =========================================================================
    # Convenience
    # =========================================================================

    def print_report(
        self,
    ):

        report = self.report()

        print(
            "\n"
            "========================================"
        )

        print(
            "SQLITE OPERATION PROFILE"
        )

        print(
            "========================================"
        )

        for (
            name,
            metrics
        ) in report[
            "operations"
        ].items():

            print()

            print(
                f"{name}"
            )

            print(
                f"  avg={metrics['avg_ms']}ms "
                f"p95={metrics['p95_ms']}ms "
                f"p99={metrics['p99_ms']}ms"
            )

            print(
                f"  executions="
                f"{metrics['executions']}"
            )

        print()

        print(
            "SQLite Statistics"
        )

        for (
            key,
            value
        ) in report[
            "sqlite"
        ].items():

            print(
                f"  {key}: {value}"
            )

        print(
            "========================================"
        )


# =============================================================================
# Instrumented Connection
# =============================================================================

class InstrumentedSQLiteConnection:

    """
    Optional wrapper around sqlite3.

    Can be injected into
    registry/queue for
    deep diagnostics.
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        profiler: SQLiteOperationProfiler,
    ):

        self.conn = conn

        self.profiler = profiler

    def execute(
        self,
        *args,
        **kwargs,
    ):

        start = (
            time.perf_counter()
        )

        result = self.conn.execute(
            *args,
            **kwargs,
        )

        self.profiler.record_execute(
            (
                time.perf_counter()
                - start
            )
            * 1000
        )

        return result

    def executemany(
        self,
        *args,
        **kwargs,
    ):

        start = (
            time.perf_counter()
        )

        result = (
            self.conn.executemany(
                *args,
                **kwargs,
            )
        )

        self.profiler.record_executemany(
            (
                time.perf_counter()
                - start
            )
            * 1000
        )

        return result

    def commit(
        self,
    ):

        start = (
            time.perf_counter()
        )

        self.conn.commit()

        self.profiler.record_commit(
            (
                time.perf_counter()
                - start
            )
            * 1000
        )

    def rollback(
        self,
    ):

        self.conn.rollback()

        self.profiler.record_rollback()

    def close(
        self,
    ):

        start = (
            time.perf_counter()
        )

        self.conn.close()

        self.profiler\
            .record_connection_close(
                (
                    time.perf_counter()
                    - start
                )
                * 1000
            )