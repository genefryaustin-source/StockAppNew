from __future__ import annotations

import streamlit as st

from .legal_permissions import LegalPrincipal, can_view_health
from .legal_workflow_runtime import LegalWorkflowRuntime


def render_legal_persistence_status(
    *,
    principal: LegalPrincipal,
    runtime: LegalWorkflowRuntime,
) -> None:
    if not can_view_health(principal):
        return

    with st.expander("Legal Workflow Persistence", expanded=False):
        if runtime.persistence_mode == "sqlalchemy":
            st.success(
                "Legal workflow persistence is connected to SQLAlchemy."
            )
        else:
            st.warning(
                "Legal workflow persistence is using memory only. "
                "Records will reset when the Streamlit process restarts."
            )
