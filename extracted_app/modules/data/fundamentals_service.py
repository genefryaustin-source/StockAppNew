import requests
import streamlit as st
from datetime import datetime, UTC
from sqlalchemy.orm import Session
import yfinance as yf

from modules.institutional.models import FundamentalSnapshot

BASE_URL = "https://api.massive.com"
TIMEOUT = 20

print("LOADED FUNDAMENTALS FROM:", __file__)

# =========================================================
# API KEY
# =========================================================

def _get_api_key():
    md = st.secrets.get("market_data", {})
    key = md.get("MASSIVE_API_KEY") or md.get("POLYGON_API_KEY")
    if not key:
        raise Exception("Missing Massive API key in secrets.toml")
    return key


def _http_get(url: str, params: dict):
    r = requests.get(url, params=params, timeout=TIMEOUT)

    if r.status_code == 429:
        import time, random
        time.sleep(2 + random.uniform(0.5, 1.5))
        r = requests.get(url, params=params, timeout=TIMEOUT)

    return r


# =========================================================
# PRICE
# =========================================================

def _massive_prev_close(symbol: str) -> float | None:
    api_key = _get_api_key()
    sym = symbol.upper()

    url = f"{BASE_URL}/v2/aggs/ticker/{sym}/prev"
    r = _http_get(url, {"adjusted": "true", "apiKey": api_key})

    if r.status_code != 200:
        return None

    try:
        data = r.json()
        results = data.get("results") or []
        if not results:
            return None

        close = results[0].get("c")
        return float(close) if close is not None else None

    except Exception:
        return None


# =========================================================
# SAFE FLOAT
# =========================================================

def _safe_float(x):
    try:
        return float(x)
    except Exception:
        return None


# =========================================================
# FCF COMPUTATION (FIXED + ROBUST)
# =========================================================

def _compute_fcf_and_margin(revenue, cfo, capex, gross_margin, op_margin):
    """
    Robust FCF calculation with fallback hierarchy
    """

    # ---------------------------------
    # CFO - CapEx (correct formula)
    # ---------------------------------
    if cfo is not None:
        try:
            capex = capex if capex is not None else 0.0
            fcf = float(cfo) - abs(float(capex))
            if revenue:
                return fcf, fcf / revenue
            return fcf, None
        except Exception:
            pass

    # ---------------------------------
    # Margin proxy fallback
    # ---------------------------------
    if gross_margin is not None and op_margin is not None:
        try:
            proxy_margin = float(gross_margin) * float(op_margin)
            if revenue:
                return proxy_margin * revenue, proxy_margin
            return None, proxy_margin
        except Exception:
            pass

    return None, None


# =========================================================
# FUNDAMENTALS INGESTION
# =========================================================

def ingest_massive_fundamentals(db: Session, tenant_id: str, symbol: str):

    api_key = _get_api_key()
    sym = symbol.upper()

    url = f"{BASE_URL}/vX/reference/financials"
    params = {
        "ticker": sym,
        "limit": 12,
        "apiKey": api_key,
    }

    r = _http_get(url, params)

    if r.status_code != 200:
        raise Exception(f"Massive Financials API error {r.status_code}: {r.text}")

    data = r.json()
    results = data.get("results", [])

    if not results:
        raise Exception(f"No financials returned for {sym}")

    latest = results[0]
    financials = latest.get("financials", {}) or {}

    income = financials.get("income_statement", {}) or {}
    cashflow = financials.get("cash_flow_statement", {}) or {}

    # -------------------------------------------------
    # REVENUE SERIES
    # -------------------------------------------------

    revenue_series = []

    for r_item in results[:5]:
        inc = (r_item.get("financials", {}) or {}).get("income_statement", {}) or {}
        rev = (inc.get("revenues") or {}).get("value") or (inc.get("revenue") or {}).get("value")

        if rev:
            val = _safe_float(rev)
            if val:
                revenue_series.append(val)

    revenue_series = list(reversed(revenue_series))
    revenue = revenue_series[-1] if revenue_series else None

    # -------------------------------------------------
    # MARGINS
    # -------------------------------------------------

    gross_margin = None
    op_margin = None

    gross_profit = _safe_float((income.get("gross_profit") or {}).get("value"))
    op_income = _safe_float((income.get("operating_income_loss") or {}).get("value"))

    if revenue:
        if gross_profit:
            gross_margin = gross_profit / revenue
        if op_income:
            op_margin = op_income / revenue

    # -------------------------------------------------
    # CASHFLOW
    # -------------------------------------------------

    cfo = _safe_float((cashflow.get("net_cash_flow_from_operating_activities") or {}).get("value"))
    capex = _safe_float((cashflow.get("capital_expenditure") or {}).get("value"))

    fcf, fcf_margin = _compute_fcf_and_margin(
        revenue,
        cfo,
        capex,
        gross_margin,
        op_margin
    )

    # -------------------------------------------------
    # YAHOO FALLBACK
    # -------------------------------------------------

    pe_ttm = None
    ps_ttm = None
    ev_ebitda = None

    try:
        ticker = yf.Ticker(sym)
        info = ticker.get_info()

        pe_ttm = info.get("trailingPE")
        ps_ttm = info.get("priceToSalesTrailing12Months")
        ev_ebitda = info.get("enterpriseToEbitda")

        if gross_margin is None:
            gross_margin = info.get("grossMargins")

        if op_margin is None:
            op_margin = info.get("operatingMargins")

    except Exception:
        pass

    # -------------------------------------------------
    # MARKET CAP
    # -------------------------------------------------

    market_cap = None

    try:
        ticker = yf.Ticker(sym)
        fast = ticker.fast_info
        shares = fast.get("shares") or fast.get("sharesOutstanding")

        last_price = _massive_prev_close(sym)

        if shares and last_price:
            market_cap = float(shares) * float(last_price)

    except Exception:
        pass

    # -------------------------------------------------
    # UPSERT
    # -------------------------------------------------

    existing = (
        db.query(FundamentalSnapshot)
        .filter(
            FundamentalSnapshot.tenant_id == tenant_id,
            FundamentalSnapshot.symbol == sym,
        )
        .first()
    )

    if existing:
        existing.market_cap = market_cap
        existing.revenue_ttm = revenue
        existing.gross_margin = gross_margin
        existing.op_margin = op_margin
        existing.fcf_margin = fcf_margin
        existing.pe_ttm = pe_ttm
        existing.asof = datetime.now(UTC)
        existing.source = "massive+yahoo_hybrid"
    else:
        snap = FundamentalSnapshot(
            tenant_id=tenant_id,
            symbol=sym,
            asof=datetime.now(UTC),
            market_cap=market_cap,
            pe_ttm=pe_ttm,
            revenue_ttm=revenue,
            gross_margin=gross_margin,
            op_margin=op_margin,
            fcf_margin=fcf_margin,
            source="massive+yahoo_hybrid",
        )
        db.add(snap)

    db.commit()

    return {
        "revenue": revenue_series,
        "gross_margin": gross_margin,
        "operating_margin": op_margin,
        "fcf": fcf,
        "fcf_margin": fcf_margin,
        "pe_ttm": pe_ttm,
        "ps_ttm": ps_ttm,
        "ev_ebitda": ev_ebitda,
    }