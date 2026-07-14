"""
modules/forex/forex_macro_calendar_engine.py

Live economic-release calendar sourced from FRED's release-dates API
(providers/fred_provider.py). Previously this returned three hardcoded rows;
it now looks up real FRED release ids by name (no guessed numeric ids) and
returns their actual recent/upcoming release dates.

Coverage note: FRED's release catalog is overwhelmingly U.S. macro data
(BLS/BEA/Census/Federal Reserve). This gives a genuinely live USD calendar,
but it is NOT a substitute for a full multi-currency economic calendar --
there is no live source wired in yet for non-USD scheduled releases (ECB/
BOE/BOJ/RBA meeting calendars, etc.). That gap is surfaced via
"coverage_note" / "fred_configured" rather than being papered over with
invented EUR/GBP/JPY calendar rows.
"""

from __future__ import annotations
from datetime import datetime, timezone

from modules.forex.providers import fred_provider

# release name (substring match against FRED's release catalog) -> impact
RELEASE_KEYWORDS = {
    "Employment Situation": "High",
    "Consumer Price Index": "High",
    "Gross Domestic Product": "High",
    "Personal Income and Outlays": "Medium",
    "Advance Monthly Sales for Retail": "Medium",
    "Producer Price Index": "Medium",
}


class ForexMacroCalendarEngine:

    def __init__(self, db=None):
        self.db = db

    def calendar(self, force_refresh: bool = False):
        events = []
        errors = []

        if not fred_provider.is_configured():
            return {
                "status": "ERROR",
                "source": "fred",
                "fred_configured": False,
                "events": [],
                "errors": ["FRED_API_KEY not configured"],
                "coverage_note": (
                    "No live economic-calendar source is configured. "
                    "Set FRED_API_KEY to enable the live USD release calendar."
                ),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

        releases_payload = fred_provider.list_releases()
        catalog = releases_payload.get("releases", []) if isinstance(releases_payload, dict) else []

        for name, impact in RELEASE_KEYWORDS.items():
            release_id = None
            for r in catalog:
                if name.lower() in str(r.get("name", "")).lower():
                    release_id = r.get("id")
                    break

            if release_id is None:
                errors.append(f"Release not found in FRED catalog: {name}")
                continue

            dates_payload = fred_provider.release_dates(release_id, limit=4)
            if dates_payload.get("error"):
                errors.append(f"{name}: {dates_payload['error']}")
                continue

            for d in dates_payload.get("dates", []):
                events.append({
                    "date": d.get("date"),
                    "currency": "USD",
                    "event": name,
                    "impact": impact,
                })

        events.sort(key=lambda e: e.get("date") or "", reverse=True)

        return {
            "status": "READY" if events else "NO_DATA",
            "source": "fred",
            "fred_configured": True,
            "events": events[:12],
            "errors": errors,
            "coverage_note": (
                "Live FRED release calendar -- covers USD macro releases only. "
                "No live source is wired in yet for non-USD scheduled events."
            ),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


_ENGINE = None


def get_forex_macro_calendar_engine(db=None):
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None):
        _ENGINE = ForexMacroCalendarEngine(db=db)
    return _ENGINE