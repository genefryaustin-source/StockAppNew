from modules.legal_portal import (
    DEFAULT_RETENTION_RULES,
    build_retention_plan,
)

# Supply records as:
# (record_type, record_id, occurred_at_iso, legal_hold)
records = []

for rule in DEFAULT_RETENTION_RULES:
    plan = build_retention_plan(
        records=records,
        rule=rule,
    )

    print(
        rule.retention_class.value,
        "eligible=",
        plan.eligible_count,
        "held=",
        plan.held_count,
    )

# This script intentionally performs no deletion.
