"""
patch_legal_nav_integration.py

Wires "Legal Operations Control" and "Legal Backup & Recovery" into
app.py's sidebar navigation and page dispatch. Both dashboards
(modules.legal_portal.render_legal_operations_dashboard and
render_legal_recovery_dashboard) existed in the codebase and were
exported, but were never connected to any page -- the only place either
was referenced was a commented-out example in
integration/persistent-operations-runtime.integration.py. Both dashboards
self-gate on LegalPrincipal.is_super_admin via can_manage_legal_portal(),
so wiring them in for all non-client-role users is safe -- a tenant_admin
clicking through will just see "Super administrator permission is
required."

Run from the repo root: python patch_legal_nav_integration.py
"""

import sys

PATH = "app.py"

with open(PATH, "r", encoding="utf-8") as f:
    content = f.read()

original = content

replacements = [
    (
        '"Portfolio Construction OS","Autonomous PM","Fund Operations","Hedge Fund OS",\n'
        '            "Legal Portal","Help",\n'
        '        ]',
        '"Portfolio Construction OS","Autonomous PM","Fund Operations","Hedge Fund OS",\n'
        '            "Legal Portal","Legal Operations Control","Legal Backup & Recovery","Help",\n'
        '        ]',
    ),
    (
        '("\u2696\ufe0f Legal & Compliance", [\n'
        '                "Legal Portal",\n'
        '            ]),',
        '("\u2696\ufe0f Legal & Compliance", [\n'
        '                "Legal Portal","Legal Operations Control","Legal Backup & Recovery",\n'
        '            ]),',
    ),
    (
        '    market_data_service = get_market_data_service()',
        '    @st.cache_resource\n'
        '    def get_legal_operations_runtime():\n'
        '        from modules.legal_portal import build_legal_operations_runtime\n'
        '        return build_legal_operations_runtime(session_factory=SessionLocal)\n'
        '\n\n'
        '    market_data_service = get_market_data_service()',
    ),
    (
        '    elif page == "Legal Portal":\n'
        '        # Navigation normally opens the public query-parameter route directly.\n'
        '        # This branch is a safeguard for an older/stale nav_page session value.\n'
        '        st.query_params["page"] = "legal"\n'
        '        st.query_params["legal_document"] = "privacy-policy"\n'
        '        st.session_state["legal_portal_active"] = True\n'
        '        st.rerun()\n'
        '\n'
        '    elif page == "Help":',
        '    elif page == "Legal Portal":\n'
        '        # Navigation normally opens the public query-parameter route directly.\n'
        '        # This branch is a safeguard for an older/stale nav_page session value.\n'
        '        st.query_params["page"] = "legal"\n'
        '        st.query_params["legal_document"] = "privacy-policy"\n'
        '        st.session_state["legal_portal_active"] = True\n'
        '        st.rerun()\n'
        '\n'
        '    elif page == "Legal Operations Control":\n'
        '        from modules.legal_portal import (\n'
        '            get_legal_workflow_runtime,\n'
        '            principal_from_user,\n'
        '            render_legal_operations_dashboard,\n'
        '        )\n'
        '        _legal_workflow_runtime = get_legal_workflow_runtime(session_factory=SessionLocal)\n'
        '        _legal_operations_runtime = get_legal_operations_runtime()\n'
        '        _legal_principal = principal_from_user(user)\n'
        '        render_legal_operations_dashboard(\n'
        '            principal=_legal_principal,\n'
        '            workflow_service=_legal_workflow_runtime.service,\n'
        '            override_service=_legal_operations_runtime.override_service,\n'
        '        )\n'
        '\n'
        '    elif page == "Legal Backup & Recovery":\n'
        '        from modules.legal_portal import (\n'
        '            get_legal_workflow_runtime,\n'
        '            principal_from_user,\n'
        '            render_legal_recovery_dashboard,\n'
        '        )\n'
        '        _legal_workflow_runtime = get_legal_workflow_runtime(session_factory=SessionLocal)\n'
        '        _legal_principal = principal_from_user(user)\n'
        '        render_legal_recovery_dashboard(\n'
        '            principal=_legal_principal,\n'
        '            service=_legal_workflow_runtime.service,\n'
        '        )\n'
        '\n'
        '    elif page == "Help":',
    ),
]

for i, (find, replace) in enumerate(replacements, start=1):
    if find not in content:
        print(f"FAILED: anchor #{i} not found, no changes made to disk.")
        sys.exit(1)
    if content.count(find) > 1:
        print(f"FAILED: anchor #{i} matched more than once (ambiguous), no changes made to disk.")
        sys.exit(1)
    content = content.replace(find, replace)

with open(PATH, "w", encoding="utf-8") as f:
    f.write(content)

print("All 4 patches applied successfully.")