# ============================================================
# fundamentals.py
# Massive Fundamentals Ingestion
# ============================================================

import requests
import os
import streamlit as st

from datetime import datetime, timedelta, UTC
from sqlalchemy.orm import Session

from modules.institutional.models import FundamentalSnapshot


BASE_URL = "https://api.massive.com"


# ============================================================
# API KEY
# ============================================================

from modules.utils.config import get_secret

def get_massive_api_key():

    key = get_secret("MASSIVE_API_KEY")

    print("🔥 FUNDAMENTALS KEY (runtime):", key)

    if not key:
        raise Exception("Massive API key not found")

    return key


# ============================================================
# SECTOR MAPPING
# ============================================================

SECTOR_MAP = {

    "ELECTRONIC COMPUTERS": "Technology",
    "COMPUTER HARDWARE": "Technology",
    "COMPUTER SOFTWARE": "Technology",
    "SEMICONDUCTORS": "Technology",

    "NATIONAL COMMERCIAL BANKS": "Financials",

    "PHARMACEUTICAL PREPARATIONS": "Healthcare",
    "BIOLOGICAL PRODUCTS": "Healthcare",

    "CRUDE PETROLEUM": "Energy",
}


def map_sector(raw):

    if not raw:
        return None

    raw = raw.upper()

    return SECTOR_MAP.get(raw, raw)


# ============================================================
# HELPER
# ============================================================

def safe_value(node):

    if isinstance(node, dict):

        return node.get("value")

    return None


# ============================================================
# INGEST FUNDAMENTALS
# ============================================================

def ingest_massive_fundamentals(db: Session, tenant_id: str, symbol: str):

    api_key = get_massive_api_key()

    symbol = symbol.upper()

    st.write(f"Fetching fundamentals for {symbol}")

    # ---------------------------------
    # Ticker reference
    # ---------------------------------

    ticker_url = f"{BASE_URL}/v3/reference/tickers/{symbol}"

    r = requests.get(

        ticker_url,

        params={"apiKey": api_key},

        timeout=15

    )

    if r.status_code != 200:

        raise Exception(f"Ticker API error: {r.text}")

    ticker = r.json().get("results", {})

    raw_sector = ticker.get("sic_description")

    sector = map_sector(raw_sector)

    market_cap = ticker.get("market_cap")

    shares = ticker.get("weighted_shares_outstanding")

    st.write(f"Sector detected: {raw_sector} → mapped: {sector}")

    # ---------------------------------
    # Financials
    # ---------------------------------

    fin_url = f"{BASE_URL}/vX/reference/financials"

    r = requests.get(

        fin_url,

        params={

            "ticker": symbol,

            "limit": 1,

            "apiKey": api_key

        },

        timeout=15

    )

    if r.status_code != 200:

        raise Exception(f"Financial API error: {r.text}")

    results = r.json().get("results", [])

    if not results:

        raise Exception("No financials returned")

    item = results[0]

    financials = item.get("financials", {})

    income = financials.get("income_statement", {})

    balance = financials.get("balance_sheet", {})

    cashflow = financials.get("cash_flow_statement", {})

    revenue = safe_value(income.get("revenues"))

    gross_profit = safe_value(income.get("gross_profit"))

    operating_income = safe_value(income.get("operating_income_loss"))

    net_income = safe_value(income.get("net_income_loss"))

    ebitda = safe_value(income.get("ebitda"))

    operating_cash = safe_value(

        cashflow.get("net_cash_flow_from_operating_activities")

    )

    cash = safe_value(

        balance.get("cash_and_cash_equivalents")

    )

    debt = safe_value(

        balance.get("long_term_debt")

    )

    # ---------------------------------
    # Margins
    # ---------------------------------

    gross_margin = None

    op_margin = None

    fcf_margin = None

    if revenue and gross_profit:

        gross_margin = gross_profit / revenue

    if revenue and operating_income:

        op_margin = operating_income / revenue

    if revenue and operating_cash:

        fcf_margin = operating_cash / revenue

    # ---------------------------------
    # Store snapshot
    # ---------------------------------

    existing = (
        db.query(FundamentalSnapshot)
        .filter(
            FundamentalSnapshot.tenant_id == tenant_id,
            FundamentalSnapshot.symbol == symbol,
        )
        .first()
    )

    if existing:
        existing.asof = datetime.now(UTC)
        existing.market_cap = market_cap
        existing.revenue_ttm = revenue
        existing.net_income = net_income
        existing.ebitda = ebitda
        existing.shares_outstanding = shares
        existing.cash = cash
        existing.total_debt = debt
        existing.sector = sector
        existing.gross_margin = gross_margin
        existing.op_margin = op_margin
        existing.fcf_margin = fcf_margin
    else:
        snap = FundamentalSnapshot(

            tenant_id=tenant_id,
            symbol=symbol,
            asof=datetime.now(UTC),
            market_cap=market_cap,
            revenue_ttm=revenue,
            net_income=net_income,
            ebitda=ebitda,
            shares_outstanding=shares,
            cash=cash,
            total_debt=debt,
            sector=sector,
            gross_margin=gross_margin,
            op_margin=op_margin,
            fcf_margin=fcf_margin,

        )

        db.add(snap)

    db.commit()

    st.success(f"Fundamentals stored. Sector: {sector}")


# ============================================================
# SNAPSHOT CACHE
# ============================================================

def latest_snapshot(

        db: Session,

        tenant_id: str,

        symbol: str,

        max_age_hours: int = 24

):

    cutoff = datetime.now(UTC) - timedelta(hours=max_age_hours)

    return (

        db.query(FundamentalSnapshot)

        .filter(

            FundamentalSnapshot.tenant_id == tenant_id,

            FundamentalSnapshot.symbol == symbol.upper(),

            FundamentalSnapshot.asof >= cutoff,

        )

        .order_by(FundamentalSnapshot.asof.desc())

        .first()

    )