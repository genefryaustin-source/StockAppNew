"""
modules/forex/providers/fred_provider.py

Live central-bank policy rate / economic-release-calendar data sourced from
the St. Louis Fed's FRED API (https://fred.stlouisfed.org).

This replaces the hand-written static tables that used to live in
forex_central_bank_engine.py and forex_macro_calendar_engine.py.

FRED_API_KEY is resolved the same way every other Forex provider resolves
its key (env var first, then Streamlit secrets.toml -- see
providers/common.py::env_key), so it is picked up automatically wherever it
is already configured for this app.
"""

from __future__ import annotations

from typing import Any, Optional

from modules.forex.providers.common import (
    env_key,
    provider_error,
    provider_headers,
    request_json,
    utc_iso,
)

BASE_URL = "https://api.stlouisfed.org/fred"
PROVIDER = "fred"


def _api_key() -> str:
    return env_key("FRED_API_KEY", "FRED_KEY", "STLOUISFED_API_KEY")


def is_configured() -> bool:
    return bool(_api_key())


def _get(path: str, **params: Any) -> dict[str, Any]:
    key = _api_key()
    if not key:
        return {"error": "FRED API key not configured (FRED_API_KEY)."}
    query = {"api_key": key, "file_type": "json", **params}
    try:
        return request_json(f"{BASE_URL}/{path}", params=query, headers=provider_headers(), timeout=20)
    except Exception as exc:
        return {"error": str(exc)}


def latest_observation(series_id: str) -> dict[str, Any]:
    """
    Most recent real value for a FRED series (e.g. FEDFUNDS, ECBDFR).
    Returns {"series_id", "value", "date", "provider"} or {"error": ...}.
    """
    data = _get(
        "series/observations",
        series_id=series_id,
        sort_order="desc",
        limit=1,
    )
    if "error" in data:
        return provider_error(PROVIDER, data["error"], raw=data)

    obs = data.get("observations") or []
    if not obs:
        return provider_error(PROVIDER, f"FRED returned no observations for {series_id}", raw=data)

    row = obs[0]
    raw_value = row.get("value")
    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        return provider_error(PROVIDER, f"FRED series {series_id} has no numeric latest value ('{raw_value}')", raw=data)

    return {
        "provider": PROVIDER,
        "series_id": series_id,
        "value": value,
        "date": row.get("date"),
        "timestamp": utc_iso(),
    }


def list_releases() -> dict[str, Any]:
    """All FRED economic-release series (id + name), used to find release
    ids by name instead of hardcoding numeric ids that could drift/expire."""
    data = _get("releases", limit=1000)
    if "error" in data:
        return provider_error(PROVIDER, data["error"], raw=data)
    releases = data.get("releases") or []
    return {"provider": PROVIDER, "releases": releases, "timestamp": utc_iso()}


def find_release_id(name_contains: str) -> Optional[int]:
    releases = list_releases()
    for r in releases.get("releases", []) if isinstance(releases, dict) else []:
        if name_contains.lower() in str(r.get("name", "")).lower():
            return r.get("id")
    return None


def release_dates(release_id: int, limit: int = 8) -> dict[str, Any]:
    data = _get(
        "release/dates",
        release_id=release_id,
        sort_order="desc",
        limit=limit,
        include_release_dates_with_no_data="true",
    )
    if "error" in data:
        return provider_error(PROVIDER, data["error"], raw=data)
    dates = data.get("release_dates") or []
    return {"provider": PROVIDER, "release_id": release_id, "dates": dates, "timestamp": utc_iso()}


def health_check() -> dict[str, Any]:
    if not is_configured():
        return {"provider": PROVIDER, "healthy": False, "error": "FRED_API_KEY not configured"}
    obs = latest_observation("FEDFUNDS")
    return {"provider": PROVIDER, "healthy": not bool(obs.get("error")), "sample": obs}