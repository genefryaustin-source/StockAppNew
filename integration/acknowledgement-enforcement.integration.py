from modules.legal_portal import (
    LegalEnforcementPolicy,
    enforce_legal_acknowledgements,
    get_legal_workflow_runtime,
    principal_from_user,
)


runtime = get_legal_workflow_runtime()
principal = principal_from_user(st.session_state.get("user"))

policy = LegalEnforcementPolicy(
    required_document_keys=(
        "terms-of-service",
        "privacy-policy",
        "financial-disclaimer",
        "risk-disclosure",
        "ai-disclosure",
    ),
    block_on_decline=True,
    block_on_overdue=True,
    enforcement_enabled=False,  # Keep False until counsel approves enforcement.
)

allowed = enforce_legal_acknowledgements(
    principal=principal,
    service=runtime.service,
    policy=policy,
)

if not allowed:
    st.stop()
