# ============================================================
# modules/preipo/service.py
# Pre-IPO Intelligence Service Layer
# ============================================================

from __future__ import annotations

import json
from datetime import datetime, UTC
from typing import Any, Dict, List, Optional

import pandas as pd
from sqlalchemy.orm import Session

from modules.preipo.models import (
    PreIPOCompany,
    PreIPOFiling,
    PreIPOFundingRound,
    PreIPOWatchlistItem,
)
from modules.preipo.scoring import score_preipo_company
from modules.preipo.ipo_intelligence_engine import (
    enrich_dataframe as intelligence_enrich_dataframe,
    top_candidates as intelligence_top_candidates,
    intelligence_metrics as intelligence_summary_metrics,
    sector_breakdown as intelligence_sector_breakdown,
    maturity_breakdown as intelligence_maturity_breakdown,
    probability_distribution as intelligence_probability_distribution,
    pipeline_funnel as intelligence_pipeline_funnel,
    underwriter_leaderboard as intelligence_underwriter_leaderboard,
)
from modules.preipo.providers.manual_provider import normalize_manual_company
from modules.preipo.providers.sec_edgar import (
    fetch_recent_ipo_candidates,
    fetch_recent_ipo_filings_for_cik,
    search_sec_company_index,
)


def _now_utc():
    return datetime.now(UTC)


def _norm(value: Any) -> str:
    return str(value or "").strip().upper()


def _safe_dt(value: Any):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        text = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    except Exception:
        return None


def _filing_stage(form_type: Optional[str]) -> str:
    form = str(form_type or "").upper().strip()
    if form in {"S-1", "F-1"}:
        return "filed"
    if form in {"S-1/A", "F-1/A", "S-4/A"}:
        return "amended"
    if form in {"424B4", "424B3", "424B1"}:
        return "priced/prospectus"
    if form in {"S-4"}:
        return "spac/merger"
    return "filed"


def upsert_preipo_company(
    db: Session,
    tenant_id: str,
    row: Dict[str, Any],
) -> PreIPOCompany:
    normalized = _norm(row.get("normalized_name") or row.get("company_name"))
    company_name = str(row.get("company_name") or normalized or "Unknown").strip()

    existing = (
        db.query(PreIPOCompany)
        .filter(
            PreIPOCompany.tenant_id == tenant_id,
            PreIPOCompany.normalized_name == normalized,
        )
        .first()
    )

    company = existing or PreIPOCompany(
        tenant_id=tenant_id,
        normalized_name=normalized,
        company_name=company_name,
    )

    for field in [
        "ticker_hint", "sector", "industry", "country", "website",
        "last_known_valuation", "last_funding_amount", "last_funding_date",
        "last_funding_round", "lead_investors", "sec_filing_status",
        "latest_sec_filing_date", "latest_sec_filing_type", "latest_sec_filing_url",
        "source", "raw_payload",
    ]:
        if field in row:
            setattr(company, field, row.get(field))

    scoring = score_preipo_company({
        "last_known_valuation": company.last_known_valuation,
        "last_funding_amount": company.last_funding_amount,
        "last_funding_date": company.last_funding_date,
        "sec_filing_status": company.sec_filing_status,
        "latest_sec_filing_type": company.latest_sec_filing_type,
        "source": company.source,
    })

    company.ipo_probability_score = scoring["ipo_probability_score"]
    company.ipo_readiness_score = scoring["ipo_readiness_score"]
    company.expected_ipo_window = scoring["expected_ipo_window"]
    company.confidence = scoring["confidence"]
    company.updated_at = _now_utc()

    if existing is None:
        db.add(company)
        db.flush()

    return company


def add_manual_preipo_company(
    db: Session,
    tenant_id: str,
    row: Dict[str, Any],
) -> PreIPOCompany:
    normalized = normalize_manual_company(row)
    company = upsert_preipo_company(db, tenant_id, normalized)
    db.commit()
    return company


def _upsert_preipo_filing(
    db: Session,
    tenant_id: str,
    filing: Dict[str, Any],
) -> tuple[PreIPOFiling, bool]:
    company_name = str(filing.get("company_name") or "Unknown").strip()
    normalized = _norm(filing.get("normalized_name") or company_name)
    accession = filing.get("accession_number")
    filing_type = filing.get("filing_type")
    filing_date = _safe_dt(filing.get("filing_date"))

    existing = None
    if accession:
        existing = (
            db.query(PreIPOFiling)
            .filter(
                PreIPOFiling.tenant_id == tenant_id,
                PreIPOFiling.accession_number == accession,
            )
            .first()
        )

    if existing is None:
        existing = (
            db.query(PreIPOFiling)
            .filter(
                PreIPOFiling.tenant_id == tenant_id,
                PreIPOFiling.normalized_name == normalized,
                PreIPOFiling.filing_type == filing_type,
                PreIPOFiling.filing_date == filing_date,
            )
            .first()
        )

    created = existing is None
    row = existing or PreIPOFiling(
        tenant_id=tenant_id,
        company_name=company_name,
        normalized_name=normalized,
        accession_number=accession,
    )

    row.company_name = company_name
    row.normalized_name = normalized
    row.filing_type = filing_type
    row.filing_date = filing_date
    row.accession_number = accession
    row.filing_url = filing.get("filing_url")
    row.cik = filing.get("cik")
    row.is_spac = bool(filing.get("is_spac"))
    row.source = filing.get("source") or "SEC_EDGAR"
    row.raw_payload = json.dumps(filing.get("raw_payload"), default=str)
    row.updated_at = _now_utc()

    if created:
        db.add(row)
        db.flush()

    company = upsert_preipo_company(db, tenant_id, {
        "company_name": company_name,
        "normalized_name": normalized,
        "sec_filing_status": _filing_stage(filing_type),
        "latest_sec_filing_date": filing_date,
        "latest_sec_filing_type": filing_type,
        "latest_sec_filing_url": filing.get("filing_url"),
        "source": row.source,
    })
    row.company_id = company.id

    return row, created


def refresh_recent_sec_discovery(
    db: Session,
    tenant_id: str,
    days: int = 90,
    form_type: Optional[str] = None,
    limit: int = 500,
) -> Dict[str, Any]:
    forms = None
    if form_type and form_type.lower() != "all":
        if form_type.upper() == "SPAC":
            forms = ["S-1", "S-1/A", "S-4", "S-4/A"]
        else:
            forms = [form_type.upper()]

    rows = fetch_recent_ipo_candidates(days=days, forms=forms, count_per_form=150)

    if form_type and form_type.upper() == "SPAC":
        rows = [row for row in rows if row.get("is_spac")]

    rows = rows[: max(int(limit), 1)]
    saved = 0
    updated = 0
    companies = set()

    try:
        seen = set()
        for filing in rows:
            key = (
                filing.get("accession_number"),
                filing.get("normalized_name"),
                filing.get("filing_type"),
                filing.get("filing_date"),
            )
            if key in seen:
                continue
            seen.add(key)

            _, created = _upsert_preipo_filing(db, tenant_id, filing)
            if created:
                saved += 1
            else:
                updated += 1
            companies.add(_norm(filing.get("company_name")))

        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "fetched": len(rows),
        "saved": saved,
        "updated": updated,
        "companies": len(companies),
    }


def refresh_sec_filings_for_company(
    db: Session,
    tenant_id: str,
    company_query: str,
) -> Dict[str, Any]:
    matches = search_sec_company_index(company_query, limit=5)
    saved = 0
    updated = 0

    try:
        for match in matches:
            filings = fetch_recent_ipo_filings_for_cik(
                match["cik"],
                company_name=match["company_name"],
            )

            for filing in filings:
                _, created = _upsert_preipo_filing(db, tenant_id, filing)
                if created:
                    saved += 1
                else:
                    updated += 1

        db.commit()
    except Exception:
        db.rollback()
        raise

    return {"matches": len(matches), "filings_saved": saved, "filings_updated": updated}


def list_preipo_filings(
    db: Session,
    tenant_id: str,
    form_type: Optional[str] = None,
    search: Optional[str] = None,
    spac_only: bool = False,
    limit: int = 500,
):
    q = db.query(PreIPOFiling).filter(PreIPOFiling.tenant_id == tenant_id)

    if form_type and form_type.lower() != "all":
        if form_type.upper() == "SPAC":
            spac_only = True
        else:
            q = q.filter(PreIPOFiling.filing_type == form_type.upper())

    if spac_only:
        q = q.filter(PreIPOFiling.is_spac == True)  # noqa: E712

    if search:
        pattern = f"%{search.strip()}%"
        q = q.filter(
            (PreIPOFiling.company_name.ilike(pattern))
            | (PreIPOFiling.filing_type.ilike(pattern))
            | (PreIPOFiling.accession_number.ilike(pattern))
        )

    return q.order_by(PreIPOFiling.filing_date.desc()).limit(limit).all()


def preipo_filings_to_dataframe(items) -> pd.DataFrame:
    rows = []
    for f in items or []:
        rows.append({
            "Company": f.company_name,
            "Form": f.filing_type,
            "Filing Date": f.filing_date,
            "CIK": getattr(f, "cik", None),
            "SPAC": bool(getattr(f, "is_spac", False)),
            "SEC Link": f.filing_url,
            "Source": f.source,
            "ID": f.id,
        })
    df = pd.DataFrame(rows)
    if not df.empty and "Filing Date" in df.columns:
        df["Filing Date"] = pd.to_datetime(df["Filing Date"], errors="coerce")
    return df


def preipo_discovery_metrics(df: pd.DataFrame) -> Dict[str, Any]:
    if df is None or df.empty:
        return {"count": 0, "s1": 0, "f1": 0, "spac": 0, "amended": 0}
    forms = df.get("Form", pd.Series(dtype=str)).fillna("").astype(str).str.upper()
    return {
        "count": int(len(df)),
        "s1": int(forms.isin(["S-1", "S-1/A"]).sum()),
        "f1": int(forms.isin(["F-1", "F-1/A"]).sum()),
        "spac": int(df.get("SPAC", pd.Series(dtype=bool)).fillna(False).astype(bool).sum()),
        "amended": int(forms.str.endswith("/A").sum()),
    }


def list_preipo_companies(
    db: Session,
    tenant_id: str,
    search: Optional[str] = None,
    min_score: Optional[float] = None,
    limit: int = 500,
):
    q = db.query(PreIPOCompany).filter(PreIPOCompany.tenant_id == tenant_id)

    if search:
        pattern = f"%{search.strip()}%"
        q = q.filter(
            (PreIPOCompany.company_name.ilike(pattern))
            | (PreIPOCompany.ticker_hint.ilike(pattern))
            | (PreIPOCompany.sector.ilike(pattern))
        )

    if min_score is not None:
        q = q.filter(PreIPOCompany.ipo_probability_score >= float(min_score))

    return (
        q.order_by(PreIPOCompany.ipo_probability_score.desc())
        .limit(limit)
        .all()
    )


def preipo_companies_to_dataframe(items) -> pd.DataFrame:
    rows = []
    for c in items or []:
        rows.append({
            "Company": c.company_name,
            "Ticker Hint": c.ticker_hint,
            "Sector": c.sector,
            "Last Valuation": c.last_known_valuation,
            "Last Funding": c.last_funding_amount,
            "Funding Date": c.last_funding_date,
            "SEC Filing": c.latest_sec_filing_type,
            "IPO Probability": c.ipo_probability_score,
            "Readiness": c.ipo_readiness_score,
            "Expected Window": c.expected_ipo_window,
            "Confidence": c.confidence,
            "Source": c.source,
            "ID": c.id,
        })
    return pd.DataFrame(rows)




# ============================================================
# Pre-IPO Intelligence Service Wrappers
# ============================================================

def enrich_preipo_filings_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    return intelligence_enrich_dataframe(df)


def top_preipo_candidates_from_filings(
    df: pd.DataFrame,
    limit: int = 25,
    min_probability: float = 0.0,
) -> pd.DataFrame:
    return intelligence_top_candidates(
        df,
        limit=limit,
        min_probability=min_probability,
    )


def preipo_intelligence_summary_metrics(df: pd.DataFrame) -> Dict[str, Any]:
    return intelligence_summary_metrics(df)


def preipo_sector_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    return intelligence_sector_breakdown(df)


def preipo_maturity_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    return intelligence_maturity_breakdown(df)


def preipo_probability_distribution(df: pd.DataFrame) -> pd.DataFrame:
    return intelligence_probability_distribution(df)


def preipo_pipeline_funnel(df: pd.DataFrame) -> pd.DataFrame:
    return intelligence_pipeline_funnel(df)


def preipo_underwriter_leaderboard(df: pd.DataFrame) -> pd.DataFrame:
    return intelligence_underwriter_leaderboard(df)


def add_preipo_watchlist_item(
    db: Session,
    tenant_id: str,
    user_id: Optional[str],
    company: PreIPOCompany,
    notes: Optional[str] = None,
) -> bool:
    existing = (
        db.query(PreIPOWatchlistItem)
        .filter(
            PreIPOWatchlistItem.tenant_id == tenant_id,
            PreIPOWatchlistItem.user_id == user_id,
            PreIPOWatchlistItem.normalized_name == company.normalized_name,
        )
        .first()
    )

    if existing:
        existing.notes = notes or existing.notes
        existing.alert_enabled = True
        existing.updated_at = _now_utc()
    else:
        db.add(PreIPOWatchlistItem(
            tenant_id=tenant_id,
            user_id=user_id,
            company_id=company.id,
            company_name=company.company_name,
            normalized_name=company.normalized_name,
            notes=notes,
            alert_enabled=True,
            status="watching",
        ))

    db.commit()
    return True


def add_preipo_filing_to_watchlist(
    db: Session,
    tenant_id: str,
    user_id: Optional[str],
    filing_id: str,
    notes: Optional[str] = None,
) -> bool:
    filing = (
        db.query(PreIPOFiling)
        .filter(
            PreIPOFiling.tenant_id == tenant_id,
            PreIPOFiling.id == filing_id,
        )
        .first()
    )
    if not filing:
        return False

    company = (
        db.query(PreIPOCompany)
        .filter(
            PreIPOCompany.tenant_id == tenant_id,
            PreIPOCompany.normalized_name == filing.normalized_name,
        )
        .first()
    )
    if company is None:
        company = upsert_preipo_company(db, tenant_id, {
            "company_name": filing.company_name,
            "normalized_name": filing.normalized_name,
            "sec_filing_status": _filing_stage(filing.filing_type),
            "latest_sec_filing_date": filing.filing_date,
            "latest_sec_filing_type": filing.filing_type,
            "latest_sec_filing_url": filing.filing_url,
            "source": filing.source,
        })
        filing.company_id = company.id
        db.commit()

    return add_preipo_watchlist_item(db, tenant_id, user_id, company, notes=notes)


def list_preipo_watchlist(
    db: Session,
    tenant_id: str,
    user_id: Optional[str] = None,
):
    q = db.query(PreIPOWatchlistItem).filter(PreIPOWatchlistItem.tenant_id == tenant_id)
    if user_id:
        q = q.filter(PreIPOWatchlistItem.user_id == user_id)
    return q.order_by(PreIPOWatchlistItem.created_at.desc()).all()
