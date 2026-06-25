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


def _safe_render(import_path: str, function_name: str, label: str, db=None, user=None):
    try:
        module = __import__(import_path, fromlist=[function_name])
        fn = getattr(module, function_name)
        try:
            return fn(db=db, user=user)
        except TypeError:
            return fn()
    except Exception as exc:
        if st is not None:
            st.error(f"{label} failed: {exc}")
            st.exception(exc)
        return {
            "status": "unavailable",
            "module": import_path,
            "function": function_name,
            "error": str(exc),
            "checked_at": _utc_now(),
        }


def render_forex_validation_workspace(db=None, user=None) -> None:
    if st is None:
        return

    st.title("Forex Validation Workspace")
    st.caption("Central QA workspace for validation, diagnostics, stress testing, resiliency, reports, and history.")

    workspace = st.radio(
        "Validation Workspace",
        [
            "Validation Center",
            "Validation Dashboard",
            "Diagnostics",
            "Stress & Performance",
            "Resiliency",
            "Reports",
        ],
        horizontal=True,
        key="forex_validation_workspace_radio",
    )

    if workspace == "Validation Center":
        return _safe_render(
            "modules.forex.forex_validation_dashboard",
            "render_forex_validation_dashboard",
            workspace,
            db=db,
            user=user,
        )

    if workspace == "Validation Dashboard":
        return _safe_render(
            "modules.forex.forex_validation_dashboard",
            "render_forex_validation_dashboard",
            workspace,
            db=db,
            user=user,
        )

    if workspace == "Diagnostics":
        Center = _safe_import("modules.forex.forex_validation_center", "ForexValidationCenter")
        result = Center().run_diagnostics()
        st.subheader("Diagnostics")
        st.json(result)
        return result

    if workspace == "Stress & Performance":
        Center = _safe_import("modules.forex.forex_validation_center", "ForexValidationCenter")
        jobs = st.selectbox("Stress Jobs", [100, 500, 1000, 5000, 10000], key="fx_val_ws_stress_jobs")
        col1, col2 = st.columns(2)
        if col1.button("Run Stress", key="fx_val_ws_run_stress"):
            st.json(Center().run_stress_test(jobs=int(jobs)))
        if col2.button("Run Benchmarks", key="fx_val_ws_run_benchmarks"):
            st.json(Center().run_benchmarks())
        return None

    if workspace == "Resiliency":
        Center = _safe_import("modules.forex.forex_validation_center", "ForexValidationCenter")
        col1, col2, col3 = st.columns(3)
        if col1.button("Run Resiliency", key="fx_val_ws_resiliency"):
            st.json(Center().run_resiliency_tests())
        if col2.button("Run Self-Healing", key="fx_val_ws_self_healing"):
            st.json(Center().run_self_healing_validation())
        if col3.button("Run Recovery", key="fx_val_ws_recovery"):
            st.json(Center().run_recovery_validation())
        return None

    Center = _safe_import("modules.forex.forex_validation_center", "ForexValidationCenter")
    st.subheader("Reports")
    if st.button("Generate Full Report Package", key="fx_val_ws_generate_report"):
        payload = Center().run_full_validation()
        st.json(Center().generate_reports(payload))
    if st.button("Save Full Validation History", key="fx_val_ws_save_history"):
        payload = Center().run_full_validation()
        st.json(Center().save_history(payload))
    return None
