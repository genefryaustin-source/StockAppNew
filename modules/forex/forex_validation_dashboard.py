from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_import(path: str, name: str):
    module = __import__(path, fromlist=[name])
    return getattr(module, name)


def _is_success(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    status = str(payload.get("status", "")).lower()
    return bool(payload.get("passed", False)) or status in {
        "pass", "passed", "success", "healthy", "clear", "completed", "certified", "exported", "saved"
    }


def _run_callable(path: str, class_name: str, method_name: str = "run_all", **kwargs) -> Dict[str, Any]:
    try:
        cls = _safe_import(path, class_name)
        instance = cls()
        method = getattr(instance, method_name)
        try:
            result = method(**kwargs)
        except TypeError:
            result = method()
        return result if isinstance(result, dict) else {"status": "completed", "result": result, "completed_at": _utc_now()}
    except Exception as exc:
        return {
            "status": "unavailable",
            "passed": False,
            "module": path,
            "class": class_name,
            "method": method_name,
            "error": str(exc),
            "checked_at": _utc_now(),
        }

try:
    import streamlit as st
except Exception:
    st = None

try:
    import pandas as pd
except Exception:
    pd = None


def _rows_from_payload(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    def walk(obj: Any, prefix: str = "") -> None:
        if isinstance(obj, dict):
            if "status" in obj or "passed" in obj:
                rows.append({
                    "name": str(obj.get("name") or obj.get("component") or prefix or "result"),
                    "status": str(obj.get("status", "unknown")),
                    "passed": _is_success(obj),
                    "checked_at": obj.get("checked_at") or obj.get("completed_at") or _utc_now(),
                    "error": obj.get("error", ""),
                })
            for key, value in obj.items():
                if isinstance(value, (dict, list)):
                    walk(value, key)
        elif isinstance(obj, list):
            for item in obj:
                walk(item, prefix)

    walk(payload)
    return rows


def _display_payload(payload: Dict[str, Any]) -> None:
    if st is None:
        return

    scorecard = payload.get("scorecard")
    if not scorecard:
        try:
            Scorecard = _safe_import("modules.forex.forex_validation_scorecard", "ForexValidationScorecard")
            scorecard = Scorecard().build(payload)
        except Exception:
            scorecard = {}

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Status", str(payload.get("status", scorecard.get("status", "unknown"))).upper())
    c2.metric("Score", f"{scorecard.get('score', 0)}%")
    c3.metric("Passed", payload.get("passed", scorecard.get("passed", 0)))
    c4.metric("Failed", payload.get("failed", scorecard.get("failed", 0)))

    rows = _rows_from_payload(payload)
    if rows:
        st.subheader("Validation Results")
        if pd is not None:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.json(rows)

    if scorecard:
        breakdown = scorecard.get("component_breakdown", [])
        if breakdown:
            st.subheader("Component Scorecard")
            if pd is not None:
                st.dataframe(pd.DataFrame(breakdown), use_container_width=True, hide_index=True)
            else:
                st.json(breakdown)

    with st.expander("Raw Payload", expanded=False):
        st.json(payload)


def render_forex_validation_dashboard(db=None, user=None) -> None:
    if st is None:
        return

    st.title("Forex Validation Dashboard")
    st.caption("One-click QA, diagnostics, stress validation, reporting, and history.")

    Center = _safe_import("modules.forex.forex_validation_center", "ForexValidationCenter")
    center = Center()

    if "forex_validation_latest_payload" not in st.session_state:
        st.session_state["forex_validation_latest_payload"] = {}

    st.subheader("System Status")
    try:
        status = center.status()
        s1, s2, s3 = st.columns(3)
        s1.metric("Overall", status.get("status", "unknown").upper())
        s2.metric("Watchdog", status.get("watchdog", {}).get("status", "unknown").upper())
        s3.metric("Anomalies", status.get("anomalies", {}).get("status", "unknown").upper())
    except Exception as exc:
        st.warning(f"Status unavailable: {exc}")

    st.divider()
    st.subheader("Validation")

    c1, c2, c3, c4 = st.columns(4)

    if c1.button("Run Full Validation", key="fx_vc_full_validation"):
        st.session_state["forex_validation_latest_payload"] = center.run_full_validation()
        st.success("Full validation completed.")

    if c2.button("Run Component Validation", key="fx_vc_component_validation"):
        st.session_state["forex_validation_latest_payload"] = {
            "status": "completed",
            "suite": "component_validation",
            "suites": {"component_validation": center.run_component_validation()},
            "completed_at": _utc_now(),
        }

    if c3.button("Run Integration Tests", key="fx_vc_integration_tests"):
        st.session_state["forex_validation_latest_payload"] = {
            "status": "completed",
            "suite": "integration_tests",
            "suites": {"integration_tests": center.run_integration_tests()},
            "completed_at": _utc_now(),
        }

    if c4.button("Run Diagnostics", key="fx_vc_diagnostics"):
        st.session_state["forex_validation_latest_payload"] = {
            "status": "completed",
            "suite": "diagnostics",
            "suites": {"diagnostics": center.run_diagnostics()},
            "completed_at": _utc_now(),
        }

    st.subheader("Stress & Performance")
    stress_jobs = st.selectbox(
        "Stress Job Count",
        [100, 500, 1000, 5000, 10000],
        index=0,
        key="fx_vc_stress_jobs",
    )

    p1, p2, p3 = st.columns(3)

    if p1.button("Run Stress Test", key="fx_vc_stress_test"):
        st.session_state["forex_validation_latest_payload"] = {
            "status": "completed",
            "suite": "stress_test",
            "suites": {"stress_test": center.run_stress_test(jobs=int(stress_jobs))},
            "completed_at": _utc_now(),
        }

    if p2.button("Run Benchmarks", key="fx_vc_benchmarks"):
        st.session_state["forex_validation_latest_payload"] = {
            "status": "completed",
            "suite": "benchmarks",
            "suites": {"benchmarks": center.run_benchmarks()},
            "completed_at": _utc_now(),
        }

    if p3.button("Full Validation + Stress", key="fx_vc_full_stress"):
        st.session_state["forex_validation_latest_payload"] = center.run_full_validation(
            include_stress=True,
            stress_jobs=int(stress_jobs),
        )

    st.subheader("Resiliency")
    r1, r2, r3, r4 = st.columns(4)

    if r1.button("Resiliency Tests", key="fx_vc_resiliency"):
        st.session_state["forex_validation_latest_payload"] = {
            "status": "completed",
            "suite": "resiliency",
            "suites": {"resiliency": center.run_resiliency_tests()},
            "completed_at": _utc_now(),
        }

    if r2.button("Self-Healing", key="fx_vc_self_healing"):
        st.session_state["forex_validation_latest_payload"] = {
            "status": "completed",
            "suite": "self_healing",
            "suites": {"self_healing": center.run_self_healing_validation()},
            "completed_at": _utc_now(),
        }

    if r3.button("Recovery", key="fx_vc_recovery"):
        st.session_state["forex_validation_latest_payload"] = {
            "status": "completed",
            "suite": "recovery",
            "suites": {"recovery": center.run_recovery_validation()},
            "completed_at": _utc_now(),
        }

    if r4.button("Watchdog", key="fx_vc_watchdog"):
        st.session_state["forex_validation_latest_payload"] = {
            "status": "completed",
            "suite": "watchdog",
            "suites": {"watchdog": center.run_watchdog()},
            "completed_at": _utc_now(),
        }

    st.divider()
    payload = st.session_state.get("forex_validation_latest_payload") or {}
    if payload:
        _display_payload(payload)

    st.subheader("Reports & History")
    q1, q2, q3 = st.columns(3)

    if q1.button("Generate Reports", key="fx_vc_generate_reports"):
        active_payload = st.session_state.get("forex_validation_latest_payload") or center.run_full_validation()
        st.json(center.generate_reports(active_payload))

    if q2.button("Save History", key="fx_vc_save_history"):
        active_payload = st.session_state.get("forex_validation_latest_payload") or center.run_full_validation()
        st.json(center.save_history(active_payload))

    if q3.button("Load Latest History", key="fx_vc_latest_history"):
        st.json(center.latest_history())
