from modules.analytics.runner import run_full_analytics


def run_incremental_analytics(db, tenant_id, symbols):

    results = {
        "processed": 0,
        "failed": 0,
    }

    for sym in symbols:

        try:
            row = run_full_analytics(db, tenant_id, sym)

            if row:
                results["processed"] += 1
            else:
                results["failed"] += 1

        except Exception as e:
            print(f"[ANALYTICS ERROR] {sym}: {e}")
            results["failed"] += 1

    return results