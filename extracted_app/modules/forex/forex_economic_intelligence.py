"""
modules/forex/forex_economic_intelligence.py

Economic and central-bank intelligence facade.

Both feeds now come from live sources instead of the hardcoded literals
this used to return unconditionally:
- high_impact_events / next_major_event -> forex_macro_calendar_engine
  (live FRED release-dates API; USD-focused -- see coverage_note).
- central_bank_events -> forex_central_bank_engine (live FRED policy-rate
  snapshot for all 8 G8 central banks). This is a live *policy rate*
  snapshot, not a scheduled meeting-date calendar -- FRED does not publish
  meeting dates for non-Fed central banks, so a true multi-bank meeting
  calendar isn't available from any live source wired into this codebase
  yet. Rows are labeled "(proxy)" when FRED has no direct feed for that
  bank's exact rate (see forex_central_bank_engine.py).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


class ForexEconomicIntelligence:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def dashboard(self, **kwargs) -> Dict[str, Any]:
        events, events_status = self._events()
        central_banks, cb_status = self._central_banks()

        return {
            "status": "READY",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "high_impact_events": events,
            "events_status": events_status,
            "central_bank_events": central_banks,
            "central_bank_status": cb_status,
            "volatility_watch": [e for e in events if e.get("impact") == "High"],
            "next_major_event": events[0] if events else {},
            "coverage_note": (
                "high_impact_events is a live FRED release calendar (USD data "
                "releases only). central_bank_events is a live FRED policy-rate "
                "snapshot for all 8 G8 banks, not a scheduled meeting-date "
                "calendar -- no live source for non-Fed meeting dates is wired "
                "in yet."
            ),
        }

    def _events(self) -> Tuple[List[Dict[str, Any]], str]:
        try:
            from modules.forex.forex_macro_calendar_engine import get_forex_macro_calendar_engine
            data = get_forex_macro_calendar_engine().calendar()
        except Exception as exc:
            return [], f"ERROR: {exc}"

        if not isinstance(data, dict):
            return [], "ERROR"
        if not data.get("fred_configured"):
            return [], "NO_API_KEY"

        events = data.get("events") or []
        return events, ("LIVE" if events else data.get("status", "NO_DATA"))

    def _central_banks(self) -> Tuple[List[Dict[str, Any]], str]:
        try:
            from modules.forex.forex_central_bank_engine import get_forex_central_bank_engine
            data = get_forex_central_bank_engine().analyze()
        except Exception as exc:
            return [], f"ERROR: {exc}"

        if not isinstance(data, dict):
            return [], "ERROR"
        if not data.get("fred_configured"):
            return [], "NO_API_KEY"

        banks = data.get("central_banks") or []
        rows: List[Dict[str, Any]] = []

        for item in banks:
            if not isinstance(item, dict):
                continue

            label = str(item.get("central_bank", "-"))
            if item.get("proxy"):
                label += " (proxy)"

            if item.get("error"):
                rows.append({
                    "date": "-",
                    "currency": item.get("currency", "-"),
                    "event": f"{label} policy rate",
                    "impact": "High",
                    "policy_rate": "unavailable",
                })
                continue

            rate = item.get("policy_rate")
            rows.append({
                "date": item.get("policy_rate_asof", "-"),
                "currency": item.get("currency", "-"),
                "event": f"{label} policy rate",
                "impact": "High",
                "policy_rate": f"{rate:.2f}%" if isinstance(rate, (int, float)) else "-",
            })

        has_live_rate = any(isinstance(item, dict) and not item.get("error") for item in banks)
        if not rows:
            status = "NO_DATA"
        elif has_live_rate:
            status = "LIVE"
        else:
            status = "ERROR"
        return rows, status


_INTEL = None


def get_forex_economic_intelligence(db: Optional[Any] = None) -> ForexEconomicIntelligence:
    global _INTEL
    if _INTEL is None or (db is not None and _INTEL.db is None):
        _INTEL = ForexEconomicIntelligence(db=db)
    return _INTEL