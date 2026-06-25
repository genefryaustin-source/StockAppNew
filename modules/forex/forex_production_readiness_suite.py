"""
modules/forex/forex_production_readiness_suite.py

Production readiness gate for the Forex subsystem.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

try:
    from modules.forex.forex_system_validation_suite import run_forex_system_validation_suite
except Exception:
    run_forex_system_validation_suite=None

try:
    from modules.forex.forex_end_to_end_test_harness import run_forex_end_to_end_test_harness
except Exception:
    run_forex_end_to_end_test_harness=None

try:
    from modules.forex.forex_performance_benchmark_suite import run_forex_performance_benchmark_suite
except Exception:
    run_forex_performance_benchmark_suite=None

try:
    from modules.forex.forex_stress_test_suite import run_forex_stress_test_suite
except Exception:
    run_forex_stress_test_suite=None

try:
    from modules.forex.forex_chaos_test_suite import run_forex_chaos_test_suite
except Exception:
    run_forex_chaos_test_suite=None

try:
    from modules.forex.forex_disaster_recovery_suite import run_forex_disaster_recovery_suite
except Exception:
    run_forex_disaster_recovery_suite=None


class ForexProductionReadinessSuite:
    def __init__(self, db=None):
        self.db=db

    def _safe_run(self, name, fn, *args, **kwargs)->Dict[str,Any]:
        if fn is None:
            return {"suite":name,"status":"MISSING","passed":0,"failed":1,"error":"Suite unavailable"}
        try:
            result=fn(*args, **kwargs)
            failed=int(result.get("failed",0) or 0)
            status="PASS" if failed==0 else "FAIL"
            return {
                "suite":name,
                "status":status,
                "passed":result.get("passed"),
                "failed":failed,
                "raw":result,
            }
        except Exception as exc:
            return {
                "suite":name,
                "status":"FAIL",
                "passed":0,
                "failed":1,
                "error":str(exc),
            }

    def run(self, live_provider_checks:bool=False, execute_paper_trade:bool=False)->Dict[str,Any]:
        suites=[
            self._safe_run(
                "Validation Suite",
                run_forex_system_validation_suite,
                db=self.db,
                run_live_provider_checks=live_provider_checks,
            ),
            self._safe_run(
                "End-to-End Tests",
                run_forex_end_to_end_test_harness,
                db=self.db,
                run_live_provider_checks=live_provider_checks,
                execute_paper_trade=execute_paper_trade,
            ),
            self._safe_run(
                "Performance Benchmarks",
                run_forex_performance_benchmark_suite,
            ),
            self._safe_run(
                "Stress Tests",
                run_forex_stress_test_suite,
            ),
            self._safe_run(
                "Chaos Tests",
                run_forex_chaos_test_suite,
            ),
            self._safe_run(
                "Disaster Recovery",
                run_forex_disaster_recovery_suite,
            ),
        ]

        total_failed=sum(int(s.get("failed") or 0) for s in suites)
        total_passed=sum(int(s.get("passed") or 0) for s in suites if s.get("passed") is not None)
        pass_suites=sum(1 for s in suites if s["status"]=="PASS")
        score=round((pass_suites/max(len(suites),1))*100,2)

        status="READY_FOR_DEPLOYMENT" if total_failed==0 and pass_suites==len(suites) else "NEEDS_REVIEW"

        return {
            "generated_at":datetime.now(timezone.utc).isoformat(),
            "production_status":status,
            "overall_score":score,
            "suite_count":len(suites),
            "passing_suites":pass_suites,
            "failing_suites":len(suites)-pass_suites,
            "total_passed_checks":total_passed,
            "total_failed_checks":total_failed,
            "providers_ready":total_failed==0,
            "analytics_ready":total_failed==0,
            "trading_ready":total_failed==0,
            "dashboards_ready":total_failed==0,
            "application_ready":total_failed==0,
            "suites":suites,
            "text_report":self.text_report(suites,score,status),
        }

    def text_report(self,suites,score,status):
        lines=[
            "====================================================",
            "FOREX PRODUCTION READINESS REPORT",
            "====================================================",
            "",
        ]
        for s in suites:
            lines.append(f"{s['suite']:<35} {s['status']}")
        lines.extend([
            "",
            f"Overall Score: {score}%",
            "",
            "PRODUCTION STATUS:",
            "READY FOR DEPLOYMENT" if status=="READY_FOR_DEPLOYMENT" else "NEEDS REVIEW",
        ])
        return "\\n".join(lines)


def run_forex_production_readiness_suite(
    db=None,
    live_provider_checks:bool=False,
    execute_paper_trade:bool=False,
):
    return ForexProductionReadinessSuite(db=db).run(
        live_provider_checks=live_provider_checks,
        execute_paper_trade=execute_paper_trade,
    )


def render_forex_production_readiness_suite(db=None):
    report=run_forex_production_readiness_suite(db=db)
    try:
        import streamlit as st
        import pandas as pd
    except Exception:
        return report

    st.title("Forex Production Readiness Suite")
    c1,c2,c3=st.columns(3)
    c1.metric("Overall Score",f"{report['overall_score']}%")
    c2.metric("Passing Suites",report["passing_suites"])
    c3.metric("Failing Suites",report["failing_suites"])

    if report["production_status"]=="READY_FOR_DEPLOYMENT":
        st.success("Forex subsystem is ready for deployment.")
    else:
        st.warning("Forex subsystem needs review before deployment.")

    st.code(report["text_report"])
    st.dataframe(pd.DataFrame(report["suites"]),use_container_width=True,hide_index=True)
    return report
