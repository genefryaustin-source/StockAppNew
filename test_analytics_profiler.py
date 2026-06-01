"""
test_analytics_profiler.py

Analytics Fabric Performance Profiler Runner

Purpose
-------
Profiles the most important Analytics Fabric operations:

    register_job()
    enqueue_job()
    claim_jobs()
    complete_job()
    recover_expired_leases()

Outputs:

    throughput/sec
    avg latency
    p50
    p95
    p99

Use this after:

    analytics_test_harness.py
    analytics_stress_test_suite.py

to identify bottlenecks.

Run:

    python test_analytics_profiler.py

or

    python test_analytics_profiler.py --iterations 5000

"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

from modules.analytics.universe_job_registry import (
    UniverseJobRegistry,
)

from modules.analytics.universe_execution_queue import (
    UniverseExecutionQueue,
)

from modules.analytics.analytics_performance_profiler import (
    AnalyticsPerformanceProfiler,
    print_performance_report,
)


# =============================================================================
# Config
# =============================================================================

DEFAULT_DB = (
    "data/analytics_profile.db"
)


# =============================================================================
# Helpers
# =============================================================================

def ensure_db_directory(
    db_path: str,
):

    db_file = Path(db_path)

    db_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )


# =============================================================================
# Runner
# =============================================================================

def run_profile(
    *,
    db_path: str,
    iterations: int,
):

    ensure_db_directory(
        db_path
    )

    print(
        "\n"
        "========================================\n"
        "ANALYTICS PERFORMANCE PROFILER\n"
        "========================================"
    )

    print(
        f"Database   : {db_path}"
    )

    print(
        f"Iterations : {iterations}"
    )

    print()

    registry = (
        UniverseJobRegistry(
            db_path=db_path
        )
    )

    queue = (
        UniverseExecutionQueue(
            registry=registry,
            db_path=db_path,
        )
    )

    profiler = (
        AnalyticsPerformanceProfiler(
            registry=registry,
            queue=queue,
        )
    )

    start = time.perf_counter()

    report = (
        profiler.run_full_profile(
            iterations=iterations
        )
    )

    elapsed = (
        time.perf_counter()
        - start
    )

    print_performance_report(
        report
    )

    print(
        "========================================"
    )

    print(
        f"Total Runtime: "
        f"{elapsed:.2f} seconds"
    )

    print(
        "========================================"
    )

    return report


# =============================================================================
# Main
# =============================================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Analytics Fabric "
            "Performance Profiler"
        )
    )

    parser.add_argument(
        "--db-path",
        default=DEFAULT_DB,
        help="Profiler database path",
    )

    parser.add_argument(
        "--iterations",
        type=int,
        default=1000,
        help="Number of operations "
             "to profile",
    )

    parser.add_argument(
        "--reset-db",
        action="store_true",
        help="Delete database before run",
    )

    args = parser.parse_args()

    if (
        args.reset_db
        and
        os.path.exists(
            args.db_path
        )
    ):

        print(
            f"Removing existing DB: "
            f"{args.db_path}"
        )

        os.remove(
            args.db_path
        )

    run_profile(
        db_path=args.db_path,
        iterations=args.iterations,
    )


if __name__ == "__main__":

    main()