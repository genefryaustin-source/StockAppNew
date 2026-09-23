from modules.legal_portal import (
    get_legal_override_service,
    get_legal_workflow_runtime,
    principal_from_user,
    render_legal_operations_dashboard,
)


runtime = get_legal_workflow_runtime()
principal = principal_from_user(st.session_state.get("user"))

# Navigation branch:
#
# elif selected_page == "Legal Operations Control":
#     render_legal_operations_dashboard(
#         principal=principal,
#         workflow_service=runtime.service,
#         override_service=get_legal_override_service(),
#     )
