from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import streamlit as st

from .legal_compliance_service import evaluate_access
from .legal_permissions import LegalPrincipal
from .legal_workflow_service import LegalWorkflowService
from .legal_override_service import LegalOverrideService


@dataclass(frozen=True)
class LegalEnforcementPolicy:
    required_document_keys: tuple[str, ...]
    block_on_decline: bool = True
    block_on_overdue: bool = True
    enforcement_enabled: bool = False


DEFAULT_POLICY = LegalEnforcementPolicy(
    required_document_keys=(
        "terms-of-service",
        "privacy-policy",
        "financial-disclaimer",
        "risk-disclosure",
        "ai-disclosure",
    ),
    block_on_decline=True,
    block_on_overdue=True,
    enforcement_enabled=False,
)


def enforce_legal_acknowledgements(
    *,
    principal: LegalPrincipal,
    service: LegalWorkflowService,
    policy: LegalEnforcementPolicy = DEFAULT_POLICY,
    override_service: LegalOverrideService | None = None,
) -> bool:
    if not policy.enforcement_enabled:
        return True

    if not principal.authenticated or not principal.user_id:
        return True

    if override_service is not None:
        active_overrides = override_service.active_for_user(
            user_id=principal.user_id,
            tenant_id=principal.tenant_id,
        )
        if active_overrides:
            st.info(
                "A temporary legal access override is active for this account."
            )
            return True

    acknowledgements = service.repository.list_acknowledgements(
        user_id=principal.user_id,
        tenant_id=principal.tenant_id,
    )

    decision = evaluate_access(
        acknowledgements=acknowledgements,
        required_document_keys=policy.required_document_keys,
        block_on_decline=policy.block_on_decline,
        block_on_overdue=policy.block_on_overdue,
    )

    if decision.allowed:
        return True

    st.error("Application access is temporarily restricted.")
    st.warning(decision.reason)
    st.caption(
        "Open Legal Acknowledgements, review the assigned documents, "
        "and record your response."
    )
    return False
