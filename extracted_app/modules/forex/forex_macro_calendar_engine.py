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

        # Resolve each keyword to a release id first -- fast, in-memory
        # string matching against the catalog already fetched above,
        # not a network call.
        release_ids: dict[str, str] = {}
        for name in RELEASE_KEYWORDS:
            for r in catalog:
                if name.lower() in str(r.get("name", "")).lower():
                    release_ids[name] = r.get("id")
                    break
            else:
                errors.append(f"Release not found in FRED catalog: {name}")

        # The actual network calls: previously these ran one at a time
        # (up to 6 sequential calls, each with a 20s timeout -- worst
        # case ~120s just for this loop), now concurrently.
        from concurrent.futures import ThreadPoolExecutor, as_completed

        with ThreadPoolExecutor(max_workers=max(1, len(release_ids))) as executor:
            futures = {
                executor.submit(fred_provider.release_dates, release_id, 4): name
                for name, release_id in release_ids.items()
            }
            for future in as_completed(futures):
                name = futures[future]
                impact = RELEASE_KEYWORDS[name]

                try:
                    dates_payload = future.result()
                except Exception as exc:
                    errors.append(f"{name}: {exc}")
                    continue

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