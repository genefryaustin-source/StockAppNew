"""
patch_legal_tables_init.py

Legal Portal's own SQLAlchemy models (LegalDocumentVersionModel,
LegalReviewModel, LegalAcknowledgementModel, LegalWorkflowEventModel,
LegalAccessOverrideModel, LegalNotificationDeliveryModel) are declared on
a separate registry, LegalWorkflowBase, not the main app's Base. Nothing
ever called create_all() for that registry, so none of those tables
existed anywhere -- surfaced as
"relation legal_access_overrides does not exist" when the newly-wired
Legal Operations Control page tried to query it. This adds the same
create_all() treatment the main Base already gets in init_database(),
using the same engine, so it's never silently missing again on any
environment.

Run from the repo root: python patch_legal_tables_init.py
"""

import sys

PATH = "modules/db/core.py"

with open(PATH, "r", encoding="utf-8") as f:
    content = f.read()

find = (
    '    Base.metadata.create_all(bind=engine)\n'
    '    print("=" * 80)\n'
    '    print("REGISTERED TABLES")\n'
    '    for t in sorted(Base.metadata.tables.keys()):\n'
    '        print(t)\n'
    '    print("=" * 80)\n'
)

replace = (
    '    Base.metadata.create_all(bind=engine)\n'
    '    print("=" * 80)\n'
    '    print("REGISTERED TABLES")\n'
    '    for t in sorted(Base.metadata.tables.keys()):\n'
    '        print(t)\n'
    '    print("=" * 80)\n'
    '\n'
    '    # Legal Portal uses its own separate SQLAlchemy registry\n'
    '    # (LegalWorkflowBase, not the main app Base above) -- create its\n'
    '    # tables here too, with the same engine, so they are never\n'
    '    # silently missing on a fresh environment.\n'
    '    from modules.legal_portal.legal_workflow_db_models import LegalWorkflowBase\n'
    '    import modules.legal_portal.legal_operations_db_models  # noqa: F401\n'
    '\n'
    '    LegalWorkflowBase.metadata.create_all(bind=engine)\n'
    '    print("=" * 80)\n'
    '    print("REGISTERED LEGAL PORTAL TABLES")\n'
    '    for t in sorted(LegalWorkflowBase.metadata.tables.keys()):\n'
    '        print(t)\n'
    '    print("=" * 80)\n'
)

if find not in content:
    print("FAILED: anchor not found, no changes made to disk.")
    sys.exit(1)
if content.count(find) > 1:
    print("FAILED: anchor matched more than once (ambiguous), no changes made to disk.")
    sys.exit(1)

content = content.replace(find, replace)

with open(PATH, "w", encoding="utf-8") as f:
    f.write(content)

print("Patch applied successfully.")