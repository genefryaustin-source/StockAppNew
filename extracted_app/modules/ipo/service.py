# ============================================================
# modules/ipo/service.py
# IPO Intelligence Service Layer
# ============================================================

from __future__ import annotations

from datetime import datetime, UTC, timedelta
from typing import Any, Dict, List, Optional

import pandas as pd
from sqlalchemy.orm import Session

from modules.ipo.models import IPOEvent, IPOWatchlistItem
from modules.ipo.providers import fetch_ipo_calendar


def _now_utc():
    return datetime.now(UTC)


def _date_str(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def _clean_symbol(value):
    if not value:
        return None
    return str(value).upper().strip()


def _upsert_ipo_event(
    db: Session,
    tenant_id: str,
    row: Dict[str, Any],
) -> IPOEvent:
    company_name = str(row.get("company_name") or "Unknown").strip()
    ipo_date = row.get("ipo_date")
    symbol = _clean_symbol(row.get("symbol"))

    existing = (
        db.query(IPOEvent)
        .filter(
            IPOEvent.tenant_id == tenant_id,
            IPOEvent.company_name == company_name,
            IPOEvent.ipo_date == ipo_date,
        )
        .first()
    )

    if existing is None and symbol:
        existing = (
            db.query(IPOEvent)
            .filter(
                IPOEvent.tenant_id == tenant_id,
                IPOEvent.symbol == symbol,
                IPOEvent.ipo_date == ipo_date,
            )
            .first()
        )

    event = existing or IPOEvent(
        tenant_id=tenant_id,
        company_name=company_name,
        ipo_date=ipo_date,
    )

    event.symbol = symbol
    event.exchange = row.get("exchange")
    event.status = row.get("status") or "upcoming"
    event.price = row.get("price")
    event.price_low = row.get("price_low")
    event.price_high = row.get("price_high")
    event.shares = row.get("shares")
    event.deal_size = row.get("deal_size")
    event.market_cap = row.get("market_cap")
    event.sector = row.get("sector")
    event.industry = row.get("industry")
    event.country = row.get("country")
    event.underwriters = row.get("underwriters")
    event.description = row.get("description")
    event.source = row.get("source")
    event.raw_payload = row.get("raw_payload")
    event.updated_at = _now_utc()

    if existing is None:
        db.add(event)
        # Flush immediately so Postgres receives one INSERT at a time.
        # Without this SQLAlchemy batches all adds into a single INSERT;
        # one UniqueViolation then aborts the entire transaction and every
        # subsequent query on the session raises PendingRollbackError.
        db.flush()

    return event


def refresh_ipo_calendar(
    db: Session,
    tenant_id: str,
    days_back: int = 30,
    days_forward: int = 180,
) -> Dict[str, Any]:
    start = _now_utc() - timedelta(days=days_back)
    end = _now_utc() + timedelta(days=days_forward)

    rows = fetch_ipo_calendar(_date_str(start), _date_str(end))

    inserted_or_updated = 0
    skipped = 0

    for row in rows:
        # Each row gets its own SAVEPOINT. A UniqueViolation or any other
        # Postgres error rolls back only that savepoint — the outer
        # transaction stays alive and the rest of the batch commits cleanly.
        sp = db.begin_nested()
        try:
            _upsert_ipo_event(db, tenant_id, row)
            sp.commit()
            inserted_or_updated += 1
        except Exception as e:
            sp.rollback()
            skipped += 1
            print("IPO UPSERT SKIPPED:", row.get("company_name"), e)

    db.commit()

    return {
        "fetched": len(rows),
        "upserted": inserted_or_updated,
        "skipped": skipped,
        "from": _date_str(start),
        "to": _date_str(end),
    }


def list_ipo_events(
    db: Session,
    tenant_id: str,
    status: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 500,
):
    q = db.query(IPOEvent).filter(IPOEvent.tenant_id == tenant_id)

    if status and status.lower() != "all":
        q = q.filter(IPOEvent.status == status)

    if search:
        pattern = f"%{search.strip()}%"
        q = q.filter(
            (IPOEvent.company_name.ilike(pattern))
            | (IPOEvent.symbol.ilike(pattern))
            | (IPOEvent.sector.ilike(pattern))
            | (IPOEvent.industry.ilike(pattern))
        )

    return q.order_by(IPOEvent.ipo_date.asc().nullslast()).limit(limit).all()


def ipo_events_to_dataframe(events) -> pd.DataFrame:
    rows = []

    for e in events or []:
        rows.append(
            {
                "Company": e.company_name,
                "Symbol": e.symbol,
                "IPO Date": e.ipo_date,
                "Exchange": e.exchange,
                "Status": e.status,
                "Price": e.price,
                "Price Low": e.price_low,
                "Price High": e.price_high,
                "Shares": e.shares,
                "Deal Size": e.deal_size,
                "Market Cap": e.market_cap,
                "Sector": e.sector,
                "Industry": e.industry,
                "Source": e.source,
            }
        )

    df = pd.DataFrame(rows)

    if not df.empty and "IPO Date" in df.columns:
        df["IPO Date"] = pd.to_datetime(df["IPO Date"], errors="coerce")

    return df


def add_to_ipo_watchlist(
    db: Session,
    tenant_id: str,
    user_id: Optional[str],
    ipo_event_id: Optional[str],
    company_name: str,
    symbol: Optional[str] = None,
    notes: Optional[str] = None,
) -> bool:
    company_name = str(company_name or "").strip()
    symbol = _clean_symbol(symbol)

    if not company_name:
        return False

    existing = (
        db.query(IPOWatchlistItem)
        .filter(
            IPOWatchlistItem.tenant_id == tenant_id,
            IPOWatchlistItem.user_id == user_id,
            IPOWatchlistItem.company_name == company_name,
        )
        .first()
    )

    if existing:
        existing.symbol = symbol or existing.symbol
        existing.ipo_event_id = ipo_event_id or existing.ipo_event_id
        existing.notes = notes or existing.notes
        existing.alert_enabled = True
        existing.updated_at = _now_utc()
    else:
        db.add(
            IPOWatchlistItem(
                tenant_id=tenant_id,
                user_id=user_id,
                ipo_event_id=ipo_event_id,
                company_name=company_name,
                symbol=symbol,
                notes=notes,
                alert_enabled=True,
                status="watching",
            )
        )

    db.commit()
    return True


def list_ipo_watchlist(
    db: Session,
    tenant_id: str,
    user_id: Optional[str] = None,
):
    q = db.query(IPOWatchlistItem).filter(IPOWatchlistItem.tenant_id == tenant_id)

    if user_id:
        q = q.filter(IPOWatchlistItem.user_id == user_id)

    return q.order_by(IPOWatchlistItem.created_at.desc()).all()


def remove_ipo_watchlist_item(
    db: Session,
    item_id: str,
) -> bool:
    item = db.query(IPOWatchlistItem).filter(IPOWatchlistItem.id == item_id).first()
    if not item:
        return False

    db.delete(item)
    db.commit()
    return True


def ipo_summary_metrics(df: pd.DataFrame) -> Dict[str, Any]:
    if df is None or df.empty:
        return {
            "count": 0,
            "total_deal_size": 0.0,
            "avg_deal_size": 0.0,
            "with_symbols": 0,
        }

    deal_size = pd.to_numeric(df.get("Deal Size"), errors="coerce") if "Deal Size" in df.columns else pd.Series(dtype=float)

    return {
        "count": int(len(df)),
        "total_deal_size": float(deal_size.sum(skipna=True)) if not deal_size.empty else 0.0,
        "avg_deal_size": float(deal_size.mean(skipna=True)) if not deal_size.empty else 0.0,
        "with_symbols": int(df["Symbol"].notna().sum()) if "Symbol" in df.columns else 0,
    }