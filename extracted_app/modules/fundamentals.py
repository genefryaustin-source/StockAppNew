# ============================================================
# FUNDAMENTALS ENGINE
# Massive (Polygon) fundamentals + sector ingestion
# ============================================================

from __future__ import annotations

import os
import requests
from datetime import datetime, UTC, timedelta
from sqlalchemy.orm import Session

from modules.institutional.models import FundamentalSnapshot


# ============================================================
# CONFIG
# ============================================================

MASSIVE_API_KEY = os.getenv("MASSIVE_API_KEY") or os.getenv("POLYGON_API_KEY")
BASE_URL = "https://api.polygon.io"


# ============================================================
# SIC → SECTOR MAP
# ============================================================

SIC_SECTOR_MAP = {
    "Electronic Computers": "Technology",
    "Computer Programming Services": "Technology",
    "Prepackaged Software": "Technology",
    "Semiconductors": "Technology",

    "Crude Petroleum and Natural Gas": "Energy",
    "Petroleum Refining": "Energy",

    "State Commercial Banks": "Financial Services",
    "National Commercial Banks": "Financial Services",
    "Insurance Carriers": "Financial Services",

    "Biological Products": "Healthcare",
    "Pharmaceutical Preparations": "Healthcare",

    "Aircraft": "Industrials",
    "Industrial Machinery": "Industrials",
}


# ============================================================
# SAFE FLOAT
# ============================================================

def _safe_float(value):
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


# ============================================================
# FETCH SECTOR FROM MASSIVE
# ============================================================

def fetch_sector(symbol: str):
    try:
        sym = symbol.upper()

        url = f"{BASE_URL}/v3/reference/tickers/{sym}"
        params = {"apiKey": MASSIVE_API_KEY}

        r = requests.get(url, params=params, timeout=20)

        if r.status_code != 200:
            print("Ticker lookup failed:", r.text)
            return None

        data = r.json()
        print("Ticker API response:", data)

        results = data.get("results")
        if not results:
            print("No results returned for ticker lookup")
            return None

        raw_sector = results.get("sic_description")
        if raw_sector:
            mapped = SIC_SECTOR_MAP.get(raw_sector, raw_sector)
            print("Sector detected:", raw_sector, "-> mapped:", mapped)
            return mapped

        print("SIC description missing")
        return None

    except Exception as e:
        print("Sector fetch error:", e)
        return None


# ============================================================
# FETCH FINANCIAL STATEMENTS
# ============================================================

def fetch_financials(symbol: str):
    sym = symbol.upper()

    url = f"{BASE_URL}/vX/reference/financials"
    params = {
        "ticker": sym,
        "limit": 8,
        "apiKey": MASSIVE_API_KEY,
    }

    r = requests.get(url, params=params, timeout=20)

    if r.status_code != 200:
        raise Exception(r.text)

    data = r.json()
    return data.get("results") or []


# ============================================================
# REVENUE SERIES
# ============================================================

def _extract_revenue_series(results):
    revenues = []

    for row in results:
        inc = (row.get("financials", {}) or {}).get("income_statement", {}) or {}
        rev = (inc.get("revenues") or {}).get("value")

        if rev is None:
            rev = (inc.get("revenue") or {}).get("value")

        rev = _safe_float(rev)
        if rev is not None:
            revenues.append(rev)

    return revenues


# ============================================================
# REVENUE TTM
# ============================================================

def compute_revenue_ttm(results):
    revenues = _extract_revenue_series(results)

    if len(revenues) >= 4:
        return sum(revenues[:4])

    return None


# ============================================================
# REVENUE CAGR
# ============================================================

def compute_revenue_cagr(results):
    """
    Computes a trailing annualized growth rate using two 4-quarter blocks.
    This is a 1-year CAGR-style comparison between the latest TTM and prior TTM.
    """
    revenues = _extract_revenue_series(results)

    if len(revenues) >= 8:
        latest_ttm = sum(revenues[:4])
        prior_ttm = sum(revenues[4:8])

        if prior_ttm and prior_ttm > 0:
            return (latest_ttm / prior_ttm) - 1

    return None


# ============================================================
# MARGINS
# ============================================================

def compute_margins(results):
    if not results:
        return None, None, None, None

    latest = results[0]

    financials = latest.get("financials", {}) or {}
    inc = financials.get("income_statement", {}) or {}
    cash = financials.get("cash_flow_statement", {}) or {}

    revenue = _safe_float((inc.get("revenues") or {}).get("value"))
    if revenue is None:
        revenue = _safe_float((inc.get("revenue") or {}).get("value"))

    gross = _safe_float((inc.get("gross_profit") or {}).get("value"))
    op = _safe_float((inc.get("operating_income_loss") or {}).get("value"))

    cfo = _safe_float((cash.get("net_cash_flow_from_operating_activities") or {}).get("value"))
    capex = _safe_float((cash.get("capital_expenditure") or {}).get("value"))

    if not revenue or revenue == 0:
        return None, None, None, None

    gross_margin = (gross / revenue) if gross is not None else None
    op_margin = (op / revenue) if op is not None else None

    # Correct FCF formula: CFO - |CapEx|
    fcf = None
    fcf_margin = None
    if cfo is not None:
        capex = capex if capex is not None else 0.0
        fcf = float(cfo) - abs(float(capex))
        fcf_margin = fcf / revenue

    # Final fallback proxy if direct FCF unavailable
    if fcf_margin is None and gross_margin is not None and op_margin is not None:
        try:
            fcf_margin = float(gross_margin) * float(op_margin)
        except Exception:
            fcf_margin = None

    return gross_margin, op_margin, fcf_margin, fcf


# ============================================================
# INGEST FUNDAMENTALS
# ============================================================

def ingest_massive_fundamentals(db: Session, tenant_id: str, symbol: str):
    sym = symbol.upper()

    print("\nFetching fundamentals for", sym)

    results = fetch_financials(sym)
    if not results:
        raise Exception("No financial statements returned")

    revenue_ttm = compute_revenue_ttm(results)
    revenue_cagr = compute_revenue_cagr(results)
    gross_margin, op_margin, fcf_margin, fcf = compute_margins(results)

    sector = fetch_sector(sym)
    print("Sector being saved:", sector)

    existing = (
        db.query(FundamentalSnapshot)
        .filter(
            FundamentalSnapshot.tenant_id == tenant_id,
            FundamentalSnapshot.symbol == sym,
        )
        .first()
    )

    if existing:
        existing.asof = datetime.now(UTC)
        existing.sector = sector
        existing.revenue_ttm = revenue_ttm

        # Use the field your pipeline expects now
        if hasattr(existing, "revenue_cagr"):
            existing.revenue_cagr = revenue_cagr
        elif hasattr(existing, "revenue_cagr_3y"):
            existing.revenue_cagr_3y = revenue_cagr

        existing.gross_margin = gross_margin
        existing.op_margin = op_margin
        existing.fcf_margin = fcf_margin
        snap = existing
    else:
        kwargs = dict(
            tenant_id=tenant_id,
            symbol=sym,
            asof=datetime.now(UTC),
            sector=sector,
            revenue_ttm=revenue_ttm,
            gross_margin=gross_margin,
            op_margin=op_margin,
            fcf_margin=fcf_margin,
        )

        # Use whichever column exists on the model
        if hasattr(FundamentalSnapshot, "revenue_cagr"):
            kwargs["revenue_cagr"] = revenue_cagr
        elif hasattr(FundamentalSnapshot, "revenue_cagr_3y"):
            kwargs["revenue_cagr_3y"] = revenue_cagr

        snap = FundamentalSnapshot(**kwargs)
        db.add(snap)

    db.commit()

    print("Fundamentals stored. Sector:", sector)

    return {
        "symbol": sym,
        "sector": sector,
        "revenue_ttm": revenue_ttm,
        "revenue_cagr": revenue_cagr,
        "gross_margin": gross_margin,
        "operating_margin": op_margin,
        "fcf": fcf,
        "fcf_margin": fcf_margin,
    }


# ============================================================
# LATEST SNAPSHOT
# ============================================================

def latest_snapshot(db: Session, tenant_id: str, symbol: str, max_age_hours: int = 72):
    cutoff = datetime.now(UTC) - timedelta(hours=max_age_hours)

    row = (
        db.query(FundamentalSnapshot)
        .filter(
            FundamentalSnapshot.tenant_id == tenant_id,
            FundamentalSnapshot.symbol == symbol.upper(),
            FundamentalSnapshot.asof >= cutoff,
        )
        .order_by(FundamentalSnapshot.asof.desc())
        .first()
    )

    return row