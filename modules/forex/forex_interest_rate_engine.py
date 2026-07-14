"""
modules/forex/forex_interest_rate_engine.py

Live G8 policy-rate table, sourced from FRED via forex_central_bank_engine
(which owns the FRED series mapping). Previously this returned a fully
hardcoded, stale rates list; it now delegates to the same live source used
by the Institutional Terminal so the two never disagree.
"""

from datetime import datetime, timezone

from modules.forex.forex_central_bank_engine import get_forex_central_bank_engine


class ForexInterestRateEngine:
    def __init__(self, db=None):
        self.db = db

    def rates(self):
        cb = get_forex_central_bank_engine()
        analysis = cb.analyze()
        banks = analysis.get("central_banks", [])

        rows = [
            {
                "currency": row.get("currency"),
                "policy_rate": row.get("policy_rate"),
                "bias": row.get("policy_bias"),
                "proxy": row.get("proxy"),
                "asof": row.get("policy_rate_asof"),
                "error": row.get("error"),
            }
            for row in banks
        ]

        return {
            "status": "READY" if any(r.get("policy_rate") is not None for r in rows) else "NO_DATA",
            "source": "fred",
            "rows": rows,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


_ENGINE = None


def get_forex_interest_rate_engine(db=None):
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None):
        _ENGINE = ForexInterestRateEngine(db=db)
    return _ENGINE