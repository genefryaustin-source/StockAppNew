from __future__ import annotations

from dataclasses import asdict

import pandas as pd
import streamlit as st

from .legal_compliance_service import (
    calculate_metrics,
    is_overdue,
)
from .legal_permissions import LegalPrincipal, can_view_health
from .legal_registry import DOCUMENTS
from .legal_workflow_service import LegalWorkflowService


def render_legal_compliance_dashboard(
    *,
    principal: LegalPrincipal,
    service: LegalWorkflowService,
) -> None:
    if not can_view_health(principal):
        st.error("Tenant administrator permission is required.")
        return

    records = service.repository.list_acknowledgements(
        tenant_id=None if principal.is_super_admin else principal.tenant_id,
    )
    metrics = calculate_metrics(records)

    st.markdown("## Legal Compliance Dashboard")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Assignments", metrics.total_assignments)
    c2.metric("Pending", metrics.pending)
    c3.metric("Accepted", metrics.accepted)
    c4.metric("Overdue", metrics.overdue)
    c5.metric("Completion", f"{metrics.completion_rate:.1f}%")

    status_tab, document_tab, tenant_tab = st.tabs(
        [
            "Acknowledgements",
            "By Document",
            "By Tenant",
        ]
    )

    with status_tab:
        rows = []

        for item in records:
            document = DOCUMENTS.get(item.document_key)

            rows.append(
                {
                    "document": (
                        document.title
                        if document
                        else item.document_key
                    ),
                    "version": item.document_version,
                    "user_id": item.user_id,
                    "tenant_id": item.tenant_id,
                    "status": item.status.value,
                    "requested_at": item.requested_at,
                    "due_at": item.due_at,
                    "responded_at": item.responded_at,
                    "overdue": is_overdue(item),
                }
            )

        if rows:
            st.dataframe(
                rows,
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No acknowledgement records are available.")

    with document_tab:
        if not records:
            st.info("No acknowledgement records are available.")
        else:
            summary: dict[str, dict[str, int]] = {}

            for item in records:
                bucket = summary.setdefault(
                    item.document_key,
                    {
                        "assignments": 0,
                        "accepted": 0,
                        "pending": 0,
                        "declined": 0,
                        "overdue": 0,
                    },
                )
                bucket["assignments"] += 1
                bucket[item.status.value] = (
                    bucket.get(item.status.value, 0) + 1
                )

                if is_overdue(item):
                    bucket["overdue"] += 1

            rows = []

            for key, values in summary.items():
                document = DOCUMENTS.get(key)
                assignments = values["assignments"]
                accepted = values.get("accepted", 0)

                rows.append(
                    {
                        "document": (
                            document.title
                            if document
                            else key
                        ),
                        **values,
                        "acceptance_rate": (
                            round(
                                (accepted / assignments) * 100.0,
                                2,
                            )
                            if assignments
                            else 0.0
                        ),
                    }
                )

            st.dataframe(
                rows,
                use_container_width=True,
                hide_index=True,
            )

    with tenant_tab:
        if not principal.is_super_admin:
            st.info(
                "Tenant-level aggregation is available to super administrators."
            )
        elif not records:
            st.info("No acknowledgement records are available.")
        else:
            tenant_summary: dict[str, dict[str, int]] = {}

            for item in records:
                tenant_key = item.tenant_id or "unassigned"
                bucket = tenant_summary.setdefault(
                    tenant_key,
                    {
                        "assignments": 0,
                        "accepted": 0,
                        "pending": 0,
                        "declined": 0,
                        "overdue": 0,
                    },
                )
                bucket["assignments"] += 1
                bucket[item.status.value] = (
                    bucket.get(item.status.value, 0) + 1
                )
                if is_overdue(item):
                    bucket["overdue"] += 1

            st.dataframe(
                [
                    {
                        "tenant_id": tenant_id,
                        **values,
                    }
                    for tenant_id, values in tenant_summary.items()
                ],
                use_container_width=True,
                hide_index=True,
            )
