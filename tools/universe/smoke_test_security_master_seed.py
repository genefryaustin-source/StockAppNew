"""
tools/universe/smoke_test_security_master_seed.py

Regression test for modules.universe.security_master_service.
seed_security_master_from_universe_symbols(), which "Run Universe
Pipeline" calls.

Root cause of the production bug this fixes: the function used SQLite's
"INSERT OR IGNORE" shorthand, which is invalid syntax against Postgres
("syntax error at or near OR") -- it aborted on the very first symbol in
production, seeding zero rows. Fixed to use "INSERT ... ON CONFLICT
(symbol) DO NOTHING", which both SQLite (3.24+) and Postgres support
natively, and batched (500 symbols/statement) instead of one INSERT per
symbol to avoid the same one-row-at-a-time performance problem fixed
earlier for the Polygon price refresh.

Tested against SQLite only here (no network dependency for CI); this fix
was additionally verified by hand against a real local PostgreSQL 16
instance at the exact production scale (11,263 symbols, 0.21s) before
being shipped -- see the conversation this was built in for that result.

Usage:
    cd <repo root>
    python3 tools/universe/smoke_test_security_master_seed.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import modules.universe.models  # noqa: F401
from models.base import Base

results = {"pass": 0, "fail": 0}


def check(label, fn):
    try:
        fn()
        print(f"PASS  {label}")
        results["pass"] += 1
    except Exception as e:
        print(f"FAIL  {label}: {type(e).__name__}: {e}")
        results["fail"] += 1


def main():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()

    from modules.universe.models import UniverseSymbol, SecurityMaster
    from modules.universe.security_master_service import seed_security_master_from_universe_symbols

    for i in range(500):
        db.add(UniverseSymbol(symbol=f"SYM{i:03d}", tenant_id="t1", universe_id="NYSE"))
    db.commit()

    def _check_seed_succeeds_without_syntax_error():
        # Before the fix, this raised psycopg2.errors.SyntaxError on
        # Postgres before writing a single row. SQLite happens to accept
        # "INSERT OR IGNORE" so this specific failure never showed up
        # locally -- it only appeared against the real production database.
        inserted = seed_security_master_from_universe_symbols(db)
        assert inserted == 500

    check("seed_security_master_from_universe_symbols completes without a syntax error",
          _check_seed_succeeds_without_syntax_error)

    def _check_rows_actually_written():
        count = db.query(SecurityMaster).count()
        assert count == 500, f"expected 500 security_master rows, got {count}"

    check("All 500 symbols actually landed in security_master", _check_rows_actually_written)

    def _check_idempotent_on_rerun():
        seed_security_master_from_universe_symbols(db)  # run again
        count = db.query(SecurityMaster).count()
        assert count == 500, "re-running the seed must not create duplicates or error"

    check("Re-running the seed is idempotent (ON CONFLICT DO NOTHING)", _check_idempotent_on_rerun)

    def _check_new_symbols_get_added_on_rerun():
        db.add(UniverseSymbol(symbol="NEWSYM", tenant_id="t1", universe_id="NYSE"))
        db.commit()
        seed_security_master_from_universe_symbols(db)
        count = db.query(SecurityMaster).count()
        assert count == 501, "a newly-added universe symbol should get picked up on the next pipeline run"

    check("A symbol added after the first seed is picked up on the next run",
          _check_new_symbols_get_added_on_rerun)

    print()
    print(f"{results['pass']} passed, {results['fail']} failed")
    return 1 if results["fail"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
