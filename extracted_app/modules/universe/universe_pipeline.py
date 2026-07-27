from modules.universe.security_master_service import (
    ensure_security_master_table,
    seed_security_master_from_universe_symbols,
)
from modules.universe.auto_assign import auto_assign_universes


# ---------------------------------------------------
# MAIN PIPELINE (THIS IS WHAT UI IMPORTS)
# ---------------------------------------------------

def run_universe_pipeline(db, tenant_id: str, limit: int = 0):
    """
    Full universe pipeline:
    1. Ensure security_master exists
    2. Seed symbols from universe_symbols
    3. Classify + assign universes
    """

    # ---------------------------------------
    # STEP 1 — Ensure table exists
    # ---------------------------------------
    ensure_security_master_table(db)

    # ---------------------------------------
    # STEP 2 — Seed symbols
    # ---------------------------------------
    seeded = seed_security_master_from_universe_symbols(db)

    # ---------------------------------------
    # STEP 3 — Classify + assign
    # ---------------------------------------
    result = auto_assign_universes(
        db,
        tenant_id=tenant_id,
        limit=limit,
    )

    return {
        "seeded": seeded,
        "total": result["total"],
        "updated": result["updated"],
    }