from modules.legal_portal import (
    LegalWorkflowService,
    get_legal_workflow_repository,
    principal_from_user,
    render_acknowledgement_banner,
    render_legal_workflow_admin,
    render_user_acknowledgements,
)


legal_workflow_service = LegalWorkflowService(
    repository=get_legal_workflow_repository(),
    # audit_sink=stockapp_legal_audit_sink,
)

principal = principal_from_user(st.session_state.get("user"))

# Add near the top of the authenticated application:
render_acknowledgement_banner(
    principal=principal,
    service=legal_workflow_service,
)

# Add navigation branches:
#
# elif selected_page == "Legal Acknowledgements":
#     render_user_acknowledgements(
#         principal=principal,
#         service=legal_workflow_service,
#     )
#
# elif selected_page == "Legal Review Workflow":
#     render_legal_workflow_admin(
#         principal=principal,
#         service=legal_workflow_service,
#     )
