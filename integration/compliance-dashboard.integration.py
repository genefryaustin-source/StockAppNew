from modules.legal_portal import (
    get_legal_workflow_runtime,
    principal_from_user,
    render_legal_compliance_dashboard,
)


runtime = get_legal_workflow_runtime()
principal = principal_from_user(st.session_state.get("user"))

# Navigation branch:
#
# elif selected_page == "Legal Compliance Dashboard":
#     render_legal_compliance_dashboard(
#         principal=principal,
#         service=runtime.service,
#     )
