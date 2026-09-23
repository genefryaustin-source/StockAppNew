from modules.legal_portal import (
    build_legal_operations_runtime,
    get_legal_workflow_runtime,
)

workflow = get_legal_workflow_runtime()
operations = build_legal_operations_runtime()

print("workflow_persistence_mode=", workflow.persistence_mode)
print("operations_persistence_mode=", operations.persistence_mode)

if workflow.persistence_mode != "sqlalchemy":
    raise SystemExit("Workflow persistence is not SQLAlchemy.")

if operations.persistence_mode != "sqlalchemy":
    raise SystemExit("Operations persistence is not SQLAlchemy.")

print("Legal persistence verification passed.")
