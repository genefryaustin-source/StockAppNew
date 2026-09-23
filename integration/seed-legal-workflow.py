from modules.legal_portal import (
    get_legal_workflow_runtime,
    seed_registered_documents,
)


runtime = get_legal_workflow_runtime()

created = seed_registered_documents(
    runtime.service,
    actor_user_id="system",
    publish=False,
)

print(f"Created {len(created)} legal document versions.")
