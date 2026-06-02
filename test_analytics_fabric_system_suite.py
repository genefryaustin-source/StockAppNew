#!/usr/bin/env python3
"""
test_analytics_fabric_system_suite.py

Analytics Fabric End-To-End Validation Runner

Usage:

    python test_analytics_fabric_system_suite.py

    python test_analytics_fabric_system_suite.py --full

    python test_analytics_fabric_system_suite.py --fail-fast

    python test_analytics_fabric_system_suite.py --export-json

    python test_analytics_fabric_system_suite.py --export-json analytics_report.json

Exit Codes:

    0 = All tests passed
    1 = One or more tests failed
    2 = Fatal execution error
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from modules.analytics.analytics_fabric_system_test_suite import (
    AnalyticsFabricSystemTestSuite,
    run_analytics_fabric_system_test_suite,
)


BANNER = """
====================================================
ANALYTICS FABRIC SYSTEM TEST SUITE
====================================================
"""


def print_banner() -> None:
    print(BANNER)


def print_result_line(result: Dict[str, Any]) -> None:
    status = result.get("status", "UNKNOWN")
    name = result.get("name", "Unnamed Test")
    duration = result.get("duration_ms", 0)

    print(
        f"{status:<8} "
        f"{name:<35} "
        f"{duration:>10.2f} ms"
    )


def print_summary(summary: Dict[str, Any]) -> None:
    passed = summary.get("passed", 0)
    failed = summary.get("failed", 0)
    warnings = summary.get("warnings", 0)
    total = summary.get("total", 0)

    success_rate = (
        round((passed / total) * 100.0, 2)
        if total > 0
        else 0.0
    )

    print()
    print("----------------------------------------------------")
    print(f"PASSED:       {passed}")
    print(f"FAILED:       {failed}")
    print(f"WARNINGS:     {warnings}")
    print(f"TOTAL:        {total}")
    print(f"SUCCESS RATE: {success_rate}%")
    print("----------------------------------------------------")
    print()


def print_failure_details(report_dict: Dict[str, Any]) -> None:
    failures = [
        result
        for result in report_dict.get("results", [])
        if result.get("status") == "FAILED"
    ]

    if not failures:
        return

    print()
    print("FAILED TEST DETAILS")
    print("----------------------------------------------------")

    for failure in failures:
        print()
        print(f"TEST: {failure.get('name')}")
        print(f"ERROR: {failure.get('message')}")

        details = failure.get("details", {})

        if details:
            print(
                json.dumps(
                    details,
                    indent=2,
                    default=str,
                )
            )

    print("----------------------------------------------------")
    print()


def export_report(
    report_dict: Dict[str, Any],
    output_file: str,
) -> None:
    path = Path(output_file)

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            report_dict,
            f,
            indent=2,
            default=str,
        )

    print(f"JSON report exported -> {path}")


def generate_executive_report(
    report_dict: Dict[str, Any],
) -> Dict[str, Any]:
    summary = report_dict.get("summary", {})

    passed = summary.get("passed", 0)
    failed = summary.get("failed", 0)
    total = summary.get("total", 0)

    success_rate = (
        round((passed / total) * 100.0, 2)
        if total > 0
        else 0.0
    )

    failed_tests = [
        item.get("name")
        for item in report_dict.get("results", [])
        if item.get("status") == "FAILED"
    ]

    return {
        "report_type": "analytics_fabric_executive_validation",
        "generated_at": datetime.utcnow().isoformat(),
        "overall_status": (
            "PASS"
            if failed == 0
            else "FAIL"
        ),
        "success_rate": success_rate,
        "passed": passed,
        "failed": failed,
        "total": total,
        "failed_tests": failed_tests,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analytics Fabric System Test Runner"
    )

    parser.add_argument(
        "--full",
        action="store_true",
        help="Run full validation suite",
    )

    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Run smoke validation mode",
    )

    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop on first failure",
    )

    parser.add_argument(
        "--export-json",
        nargs="?",
        const="analytics_fabric_system_report.json",
        help="Export report to JSON",
    )

    parser.add_argument(
        "--export-executive",
        nargs="?",
        const="analytics_fabric_executive_report.json",
        help="Export executive summary",
    )

    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Reduce console output",
    )

    parser.add_argument(
        "--db-path",
        default=None,
        help="Override temporary test database",
    )

    return parser.parse_args()


def run_suite(
    args: argparse.Namespace,
) -> int:
    db_path = args.db_path

    if db_path is None:
        db_path = str(
            Path(tempfile.gettempdir())
            / "analytics_fabric_validation.db"
        )

    suite = AnalyticsFabricSystemTestSuite(
        db_path=db_path,
        reset_db=True,
        fail_fast=args.fail_fast,
        verbose=not args.quiet,
    )

    report = suite.run_all()
    report_dict = report.as_dict()

    if not args.quiet:
        print_banner()

        for result in report_dict["results"]:
            print_result_line(result)

        print_summary(report_dict["summary"])
        print_failure_details(report_dict)

    if args.export_json:
        export_report(
            report_dict,
            args.export_json,
        )

    if args.export_executive:
        executive = generate_executive_report(
            report_dict,
        )

        export_report(
            executive,
            args.export_executive,
        )

    failed = report_dict["summary"]["failed"]

    return 0 if failed == 0 else 1


def main() -> int:
    try:
        args = parse_args()
        return run_suite(args)

    except KeyboardInterrupt:
        print()
        print("Execution cancelled by user.")
        return 2

    except Exception as exc:
        print()
        print("FATAL SUITE ERROR")
        print("----------------------------------------------------")
        print(str(exc))
        print("----------------------------------------------------")
        return 2


if __name__ == "__main__":
    sys.exit(main())