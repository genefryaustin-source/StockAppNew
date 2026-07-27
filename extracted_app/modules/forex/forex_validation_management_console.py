from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_import(path: str, name: str):
    module = __import__(path, fromlist=[name])
    return getattr(module, name)


def _status_ok(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    status = str(value.get("status", "")).lower()
    return bool(value.get("passed", False)) or status in {
        "pass", "passed", "success", "healthy", "clear", "completed",
        "certified", "ready", "approved", "online", "optimized"
    }

try:
    import streamlit as st
except Exception:
    st = None

try:
    import pandas as pd
except Exception:
    pd = None


def _require_permission(user: Any, action: str) -> Dict[str, Any]:
    Permission = _safe_import(
        "modules.forex.forex_validation_permission_engine",
        "ForexValidationPermissionEngine",
    )
    return Permission().require(user=user, action=action)


def render_forex_validation_management_console(db=None, user=None) -> None:
    if st is None:
        return

    st.title("Forex Validation Management Console")
    st.caption("Administrative console for validation operations, permissions, tenant context, cloud sync, SLA, SLO, and audit.")

    permission = _require_permission(user, "view")
    if not permission.get("allowed"):
        st.warning("You do not have permission to access the Forex Validation Management Console.")
        st.json(permission)
        return

    try:
        Audit = _safe_import(
            "modules.forex.forex_validation_audit_dashboard",
            "ForexValidationAuditLog",
        )
        Audit().record(
            event_type="console_access",
            action="view_management_console",
            user=user,
            payload={"permission": permission},
        )
    except Exception:
        pass

    workspace = st.radio(
        "Management Workspace",
        [
            "Overview",
            "Permissions",
            "Tenant Context",
            "Cloud Sync",
            "SLA / SLO",
            "Operations",
            "Audit",
        ],
        horizontal=True,
        key="fx_val_management_workspace",
    )

    if workspace == "Overview":
        Platform = _safe_import(
            "modules.forex.forex_validation_platform",
            "ForexValidationPlatform",
        )
        Ops = _safe_import(
            "modules.forex.forex_validation_operations_center",
            "ForexValidationOperationsCenter",
        )

        platform = Platform().status()
        snapshot = Ops().snapshot()
        summary = snapshot.get("summary", {})

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Platform", platform.get("status", "unknown").upper())
        c2.metric("Jobs", summary.get("scheduled_jobs", 0))
        c3.metric("Runs", summary.get("validation_runs", 0))
        c4.metric("Failed", summary.get("failed_runs", 0))

        st.json(platform)
        return

    if workspace == "Permissions":
        Permission = _safe_import(
            "modules.forex.forex_validation_permission_engine",
            "ForexValidationPermissionEngine",
        )
        engine = Permission()
        st.subheader("Current User Permission")
        st.json(engine.require(user=user, action="view"))

        st.subheader("Permission Matrix")
        matrix = engine.permission_matrix()
        rows = [
            {"role": role, "permissions": ", ".join(perms)}
            for role, perms in matrix.get("matrix", {}).items()
        ]
        if pd is not None:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.json(rows)
        return

    if workspace == "Tenant Context":
        MultiTenant = _safe_import(
            "modules.forex.forex_validation_multi_tenant",
            "ForexValidationMultiTenant",
        )
        mt = MultiTenant()
        tenant_id = st.text_input("Tenant Override", value="", key="fx_val_console_tenant_override")
        context = mt.tenant_context(user=user, tenant_id=tenant_id or None)
        st.json(context)

        if st.button("Run Tenant Snapshot", key="fx_val_console_tenant_snapshot"):
            st.json(mt.tenant_snapshot(user=user, tenant_id=tenant_id or None))
        return

    if workspace == "Cloud Sync":
        sync_permission = _require_permission(user, "reports")
        if not sync_permission.get("allowed"):
            st.warning("You do not have permission to sync validation reports.")
            st.json(sync_permission)
            return

        Cloud = _safe_import(
            "modules.forex.forex_validation_cloud_sync",
            "ForexValidationCloudSync",
        )
        cloud = Cloud()
        c1, c2, c3 = st.columns(3)
        if c1.button("Export Latest Run", key="fx_val_console_export_latest"):
            st.json(cloud.export_latest_run())
        if c2.button("Export Snapshot", key="fx_val_console_export_snapshot"):
            st.json(cloud.export_snapshot())
        if c3.button("Sync Report Package", key="fx_val_console_sync_reports"):
            st.json(cloud.sync_report_package())

        st.subheader("Cloud Sync Status")
        st.json(cloud.status())

        events = cloud.list_sync_events()
        if events:
            st.subheader("Sync Events")
            if pd is not None:
                st.dataframe(pd.DataFrame(events), use_container_width=True, hide_index=True)
            else:
                st.json(events)
        return

    if workspace == "SLA / SLO":
        SLA = _safe_import(
            "modules.forex.forex_validation_sla_engine",
            "ForexValidationSLAEngine",
        )
        SLO = _safe_import(
            "modules.forex.forex_validation_slo_engine",
            "ForexValidationSLOEngine",
        )

        sla = SLA().evaluate_all()
        slo = SLO().calculate()
        budget = SLO().error_budget()

        c1, c2, c3 = st.columns(3)
        c1.metric("SLA", sla.get("status", "unknown").upper())
        c2.metric("SLO", slo.get("status", "unknown").upper())
        c3.metric("Error Budget", budget.get("error_budget_remaining", 0))

        st.subheader("SLA")
        st.json(sla)
        st.subheader("SLO")
        st.json(slo)
        st.subheader("Error Budget")
        st.json(budget)
        return

    if workspace == "Operations":
        Ops = _safe_import(
            "modules.forex.forex_validation_operations_center",
            "ForexValidationOperationsCenter",
        )
        Runtime = _safe_import(
            "modules.forex.forex_validation_runtime_controller",
            "ForexValidationRuntimeController",
        )
        Scheduler = _safe_import(
            "modules.forex.forex_validation_scheduler",
            "ForexValidationScheduler",
        )

        c1, c2, c3 = st.columns(3)
        if c1.button("Schedule Full", key="fx_val_console_schedule_full"):
            st.json(Scheduler().schedule_full_validation())
        if c2.button("Run Validation Tick", key="fx_val_console_run_tick"):
            st.json(Runtime().tick(max_jobs=5))
        if c3.button("Run Now", key="fx_val_console_run_now"):
            st.json(Runtime().run_once())

        st.subheader("Operations Snapshot")
        st.json(Ops().snapshot())
        return

    render_audit = _safe_import(
        "modules.forex.forex_validation_audit_dashboard",
        "render_forex_validation_audit_dashboard",
    )
    return render_audit(db=db, user=user)
