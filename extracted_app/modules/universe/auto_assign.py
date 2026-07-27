from sqlalchemy import text
from modules.universe.classifier import classify_symbol
from modules.universe.security_master_service import (
    upsert_security_master_classification,
)

# ---------------------------------------------------
# UNIVERSE ID MAP
# ---------------------------------------------------

UNIVERSE_MAP = {
    "AMEX": "3ba54477-78cf-42e8-bc3d-ea5e0bc986cb",
    "NASDAQ": "a721b375-f8e3-404b-8300-64f69036ae9b",
    "NYSE": "b23b4139-5aa8-4c30-b2fc-d30a5a491bcf",
    "SP500": "e2dba1c7-a1d5-4003-a000-236504806ffc",
    "ETF": "ecb3b4c2-e8f7-489d-8221-55473edec382",
    "DEFAULT": "dbe20548-91e1-4b7b-8957-5e9adcdb9db1",
}

# Minimal S&P 500 seed (can expand later)
SP500_SET = {
    "AAPL","MSFT","NVDA","AMZN","META","GOOGL","GOOG","BRK.B",
    "LLY","AVGO","JPM","XOM","UNH","V","COST","MA","PG","HD",
    "JNJ","WMT","ABBV","BAC","KO","MRK","PEP","CVX","ADBE",
    "NFLX","AMD","TMO","LIN","CSCO","ACN","CRM","ABT","DHR",
    "MCD","WFC","DIS","TXN","PM","GE","INTU","QCOM","IBM",
}


# ---------------------------------------------------
# MAIN FUNCTION
# ---------------------------------------------------

def auto_assign_universes(db, tenant_id: str, limit: int = 0, force_rebuild: bool = False):

    query = """
        SELECT symbol, universe_id
        FROM universe_symbols
        WHERE tenant_id = :tenant_id
        ORDER BY symbol
    """

    if limit > 0:
        query += f" LIMIT {int(limit)}"

    rows = db.execute(text(query), {"tenant_id": tenant_id}).fetchall()

    total = len(rows)
    updated = 0

    for sym, current_uid in rows:

        # ---------------------------------------
        # NORMALIZE SYMBOL (CRITICAL FIX)
        # ---------------------------------------
        sym_clean = str(sym).upper().strip()

        # ---------------------------------------
        # CLASSIFY
        # ---------------------------------------
        c = classify_symbol(sym_clean, db)

        # Safety fallback (never allow None)
        exchange = c.get("exchange") or "NASDAQ"
        is_etf = bool(c.get("is_etf"))

        # ---------------------------------------
        # DETERMINE TARGET UNIVERSE
        # ---------------------------------------
        if sym_clean in SP500_SET:
            target_uid = UNIVERSE_MAP["SP500"]

        elif is_etf:
            target_uid = UNIVERSE_MAP["ETF"]

        elif exchange in UNIVERSE_MAP:
            target_uid = UNIVERSE_MAP[exchange]

        else:
            target_uid = UNIVERSE_MAP["DEFAULT"]

        # ---------------------------------------
        # UPDATE SECURITY MASTER (SAFE)
        # ---------------------------------------
        try:
            upsert_security_master_classification(
                db,
                sym_clean,
                exchange,
                is_etf,
            )
        except Exception as e:
            print(f"SECURITY MASTER FAIL: {sym_clean} -> {e}")

        # ---------------------------------------
        # UPDATE UNIVERSE ASSIGNMENT (FIXED)
        # ---------------------------------------
        try:

            should_update = force_rebuild or (current_uid != target_uid)

            if should_update:

                res = db.execute(text("""
                    UPDATE universe_symbols
                    SET universe_id = :uid
                    WHERE UPPER(TRIM(symbol)) = :sym
                      AND tenant_id = :tenant_id
                """), {
                    "uid": target_uid,
                    "sym": sym_clean,
                    "tenant_id": tenant_id,
                })

                # Debug visibility
                if res.rowcount > 0:
                    updated += res.rowcount
                else:
                    print(f"NO MATCH: {sym_clean}")

        except Exception as e:
            print(f"UPDATE FAIL: {sym_clean} -> {e}")

    # ---------------------------------------
    # FINAL COMMIT (CRITICAL)
    # ---------------------------------------
    db.commit()

    # ---------------------------------------
    # FINAL DISTRIBUTION CHECK (DEBUG)
    # ---------------------------------------
    try:
        dist = db.execute(text("""
            SELECT universe_id, COUNT(*)
            FROM universe_symbols
            GROUP BY universe_id
        """)).fetchall()

        print("UNIVERSE DISTRIBUTION:", dist)

    except Exception as e:
        print("DISTRIBUTION CHECK FAILED:", e)

    return {
        "total": total,
        "updated": updated,
    }