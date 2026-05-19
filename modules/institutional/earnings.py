import requests
from datetime import datetime, UTC
from sqlalchemy.orm import Session

from modules.institutional.models import EarningsEvent


BASE_URL = "https://api.massive.com"
TIMEOUT = 15


def _get_secret_api_key() -> str | None:
    # Import streamlit only inside runtime to avoid NameError during import tests
    try:
        import streamlit as st
        key = None

        # Preferred: st.secrets["market_data"]["MASSIVE_API_KEY"]
        try:
            key = st.secrets["market_data"].get("MASSIVE_API_KEY")
        except Exception:
            key = None

        # fallback: st.secrets["market_data"]["POLYGON_API_KEY"] (legacy)
        if not key:
            try:
                key = st.secrets["market_data"].get("POLYGON_API_KEY")
            except Exception:
                key = None

        return key
    except Exception:
        return None


def _parse_iso_date(d: str):
    if not d:
        return None
    try:
        # handle YYYY-MM-DD
        if len(d) == 10:
            return datetime.fromisoformat(d).replace(tzinfo=UTC)
        # handle full iso datetime
        return datetime.fromisoformat(d.replace("Z", "+00:00")).astimezone(UTC)
    except Exception:
        return None


def ingest_massive_earnings(db: Session, tenant_id: str, symbol: str, limit: int = 50) -> int:
    """
    Massive endpoint used: /vX/reference/financials
    This is financial filings history; Massive may not provide estimates.
    We store any EPS/revenue values we can find into eps_est/rev_est fields.
    """
    api_key = _get_secret_api_key()
    if not api_key:
        raise Exception("Massive API key missing (set market_data.MASSIVE_API_KEY in secrets.toml)")

    sym = symbol.upper()

    url = f"{BASE_URL}/vX/reference/financials"
    params = {
        "ticker": sym,
        "limit": limit,
        "apiKey": api_key,
    }

    r = requests.get(url, params=params, timeout=TIMEOUT)
    if r.status_code != 200:
        raise Exception(f"Massive Earnings API error {r.status_code}: {r.text}")

    data = r.json()
    results = data.get("results") or []
    if not results:
        return 0

    inserted = 0

    for item in results:
        filing_date = item.get("filing_date") or item.get("end_date") or item.get("period_end_date")
        event_date = _parse_iso_date(filing_date)
        if not event_date:
            continue

        exists = (
            db.query(EarningsEvent)
            .filter(
                EarningsEvent.tenant_id == tenant_id,
                EarningsEvent.symbol == sym,
                EarningsEvent.event_date == event_date,
            )
            .first()
        )
        if exists:
            continue

        financials = item.get("financials") or {}
        income = financials.get("income_statement") or {}

        # Robust parsing: Massive objects often look like {"value": ...}
        def _val(x):
            if x is None:
                return None
            if isinstance(x, dict):
                return x.get("value")
            return x

        eps_value = _val(income.get("basic_earnings_per_share")) or _val(income.get("diluted_earnings_per_share"))
        rev_value = _val(income.get("revenues")) or _val(income.get("revenue"))

        # IMPORTANT: do NOT use eps_actual/revenue_actual fields in ORM kwargs
        ev = EarningsEvent(
            tenant_id=tenant_id,
            symbol=sym,
            event_date=event_date,
            time_of_day=None,
            eps_est=_to_float_safe(eps_value),
            rev_est=_to_float_safe(rev_value),
            
        )

        db.add(ev)
        inserted += 1

    db.commit()
    return inserted


def _to_float_safe(v):
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def list_upcoming(db: Session, tenant_id: str, limit: int = 200):
    return (
        db.query(EarningsEvent)
        .filter(EarningsEvent.tenant_id == tenant_id)
        .order_by(EarningsEvent.event_date.desc())
        .limit(limit)
        .all()
    )