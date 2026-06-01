"""
test_analytics_bulk_stress_suite.py

Analytics Bulk Stress Suite Runner

Purpose
-------
Validate whether AnalyticsBulkOperations actually improves
performance versus the original per-operation APIs.

Usage
-----

Default:

    python test_analytics_bulk_stress_suite.py

Custom:

    python test_analytics_bulk_stress_suite.py --jobs 50000

Large:

    python test_analytics_bulk_stress_suite.py --jobs 100000

"""

from __future__ import annotations

import argparse
import json
import time

from modules.analytics.analytics_bulk_stress_suite import (
    AnalyticsBulkStressSuite,
    BulkStressConfig,
)


# =============================================================================
# Helpers
# =============================================================================

def print_header():

    print()
    print("=" * 60)
    print("ANALYTICS BULK STRESS VALIDATION")
    print("=" * 60)
    print()


def print_summary(results):

    print()
    print("=" * 60)
    print("BULK STRESS RESULTS")
    print("=" * 60)
    print()

    for phase, data in results.items():

        if phase == "registration_improvement":

            print(
                f"{phase:35} "
                f"{data:.2f}x"
            )

            continue

        print(
            f"{phase:35}"
        )

        print(
            f"  Operations : "
            f"{data['operation_count']:,}"
        )

        print(
            f"  Runtime    : "
            f"{data['elapsed_seconds']:.4f}s"
        )

        print(
            f"  Throughput : "
            f"{data['throughput_per_second']:,.2f} ops/sec"
        )

        print()

    print("=" * 60)
    print()


# =============================================================================
# Runner
# =============================================================================

def run_suite(
    *,
    jobs: int,
    db_path: str,
    reset_db: bool,
):

    config = BulkStressConfig(
        db_path=db_path,
        reset_db=reset_db,
        job_count=jobs,
        verbose=True,
    )

    suite = AnalyticsBulkStressSuite(
        config=config
    )

    start = time.perf_counter()

    results = suite.run()

    elapsed = (
        time.perf_counter()
        - start
    )

    print_summary(
        results
    )

    print(
        f"Total Runtime: "
        f"{elapsed:.2f} seconds"
    )

    print()

    return results


# =============================================================================
# Main
# =============================================================================

def main():

    parser = argparse.ArgumentParser(
        description=
        "Analytics Bulk Stress Suite"
    )

    parser.add_argument(
        "--jobs",
        type=int,
        default=10000,
        help="Number of jobs",
    )

    parser.add_argument(
        "--db-path",
        type=str,
        default=
        "data/analytics_bulk_stress.db",
        help="Database path",
    )

    parser.add_argument(
        "--reset-db",
        action="store_true",
        default=True,
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help=
        "Output JSON results",
    )

    args = parser.parse_args()

    print_header()

    results = run_suite(
        jobs=args.jobs,
        db_path=args.db_path,
        reset_db=args.reset_db,
    )

    if args.json:

        print(
            json.dumps(
                results,
                indent=2,
            )
        )


if __name__ == "__main__":

    main()