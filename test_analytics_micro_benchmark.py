"""
test_analytics_micro_benchmark.py

Analytics Fabric Micro Benchmark Runner

Purpose
-------
Runs isolated database write-path benchmarks against:

    UniverseJobRegistry
    UniverseExecutionQueue

This identifies exactly where the bottleneck exists.

Usage
-----

python test_analytics_micro_benchmark_V2.py

or

python test_analytics_micro_benchmark_v2.py --iterations 5000

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

from modules.analytics.analytics_micro_benchmark import (
    AnalyticsMicroBenchmark,
    print_benchmark_results,
)


DEFAULT_DB = (
    "data/analytics_micro_benchmark.db"
)


# =============================================================================
# Helpers
# =============================================================================

def ensure_parent_directory(
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

def run_benchmark(
    *,
    db_path: str,
    iterations: int,
):

    ensure_parent_directory(
        db_path
    )

    print()

    print(
        "========================================"
    )

    print(
        "ANALYTICS MICRO BENCHMARK"
    )

    print(
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

    benchmark = (
        AnalyticsMicroBenchmark(
            registry=registry,
            queue=queue,
        )
    )

    start = time.perf_counter()

    results = (
        benchmark.run_all(
            iterations=iterations
        )
    )

    elapsed = (
        time.perf_counter()
        - start
    )

    print_benchmark_results(
        results
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

    print()

    return results


# =============================================================================
# Main
# =============================================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Analytics Fabric "
            "Micro Benchmark Suite"
        )
    )

    parser.add_argument(
        "--db-path",
        default=DEFAULT_DB,
        help="Benchmark database path",
    )

    parser.add_argument(
        "--iterations",
        type=int,
        default=1000,
        help="Benchmark iterations",
    )

    parser.add_argument(
        "--reset-db",
        action="store_true",
        help=(
            "Delete existing benchmark DB"
        ),
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

    run_benchmark(
        db_path=args.db_path,
        iterations=args.iterations,
    )


if __name__ == "__main__":

    main()