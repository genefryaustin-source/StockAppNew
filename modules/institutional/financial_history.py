# ============================================================
# modules/institutional/financial_history.py
# Phase 5 - Financial History Ingestion (Massive)
# Robust parsing + rollback-safe DB writes
# ============================================================

import os
from datetime import datetime, UTC

import requests
import streamlit as st
from sqlalchemy.orm import Session

from modules.institutional.models import FinancialPeriod

BASE_URL = "https://api.massive.com"
TIMEOUT = 20


# ------------------------------
# Secrets / API key
# ------------------------------

from modules.utils.config import get_secret

def _get_massive_api_key() -> str:

    key = get_secret("MASSIVE_API_KEY")

    print("🔥 FINANCIAL HISTORY KEY (runtime):", key)

    if not key:
        raise Exception("Massive API key not found")

    return key


# ------------------------------
# Parsing helpers
# ------------------------------

def _parse_date(s: str | None):
    """
    Massive typically returns ISO dates like YYYY-MM-DD.
    Store as naive UTC datetime for consistency.
    """
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            return dt
        return dt.astimezone(UTC).replace(tzinfo=None)
    except Exception:
        return None


def _to_float(v):
    """
    Convert Massive values to float safely.
    Handles:
      - None
      - ""
      - "123"
      - numbers
      - {"value": 123}
    """
    if v is None:
        return None

    # dict like {"value": 123, "unit": "USD"}
    if isinstance(v, dict):
        v = v.get("value")

    if v is None:
        return None

    if isinstance(v, str):
        s = v.strip()
        if s == "" or s.lower() in ("null", "none", "na", "n/a"):
            return None
        try:
            return float(s)
        except Exception:
            return None

    # int/float
    try:
        return float(v)
    except Exception:
        return None


def _safe_value(node):
    """
    Wrapper for common Massive nodes.
    """
    return _to_float(node)


# ------------------------------
# Main ingestion
# ------------------------------

def ingest_massive_financial_history(
    db: Session,
    tenant_id: str,
    symbol: str,
    period_type: str = "annual",
    limit: int = 50,
):
    """
    Ingests history from:
      GET https://api.massive.com/vX/reference/financials?ticker=XXX&apiKey=YYY

    period_type controls what we STORE:
      - "annual": store only annual-like records (FY)
      - "quarterly": store only quarterly-like records (Q1-Q4)
      - "all": store everything (annual + quarterly)
    """
    sym = symbol.upper().strip()
    api_key = _get_massive_api_key()

    url = f"{BASE_URL}/vX/reference/financials"
    params = {"ticker": sym, "limit": limit, "apiKey": api_key}

    r = requests.get(url, params=params, timeout=TIMEOUT)
    if r.status_code != 200:
        raise Exception(f"Massive financials API error {r.status_code}: {r.text}")

    data = r.json()
    results = data.get("results") or []
    if not results:
        return 0

    mode = (period_type or "annual").lower().strip()
    if mode not in ("annual", "quarterly", "all"):
        mode = "annual"

    inserted = 0

    # If anything fails, we rollback and keep the session usable.
    try:
        for item in results:

            end_date = _parse_date(item.get("end_date")) or _parse_date(item.get("filing_date"))
            if not end_date:
                continue

            fiscal_year_raw = item.get("fiscal_year")
            fiscal_year = _to_float(fiscal_year_raw)  # FIX: "" becomes None instead of crash

            fiscal_period = item.get("fiscal_period") or item.get("timeframe") or ""
            fiscal_period_str = str(fiscal_period).upper().strip()

            timeframe = str(item.get("timeframe") or "").lower()

            # Detect annual vs quarterly.
            # Massive sometimes uses "TTM" rows; we skip those for history.
            if fiscal_period_str == "TTM" or "ttm" in timeframe:
                # skip TTM; it can distort CAGR and often has weird metadata
                continue

            if "quarter" in timeframe or fiscal_period_str.startswith("Q"):
                detected_type = "quarterly"
            else:
                detected_type = "annual"

            # apply filter
            if mode != "all" and detected_type != mode:
                continue

            financials = item.get("financials") or {}
            income = financials.get("income_statement") or {}
            balance = financials.get("balance_sheet") or {}
            cashflow = financials.get("cash_flow_statement") or {}

            revenue = _safe_value(income.get("revenues"))
            gross_profit = _safe_value(income.get("gross_profit"))
            operating_income = _safe_value(income.get("operating_income_loss")) or _safe_value(income.get("operating_income"))
            net_income = _safe_value(income.get("net_income_loss")) or _safe_value(income.get("net_income"))

            eps_basic = _safe_value(income.get("basic_earnings_per_share")) or _safe_value(income.get("basic_eps"))
            eps_diluted = _safe_value(income.get("diluted_earnings_per_share")) or _safe_value(income.get("diluted_eps"))

            ebitda = _safe_value(income.get("ebitda"))
            if ebitda is None and operating_income is not None:
                ebitda = operating_income

            operating_cf = (
                _safe_value(cashflow.get("net_cash_flow_from_operating_activities"))
                or _safe_value(cashflow.get("net_cash_flow_from_operating_activities_continuing"))
            )

            capex = (
                _safe_value(cashflow.get("payments_to_acquire_property_plant_and_equipment"))
                or _safe_value(cashflow.get("capital_expenditures"))
            )

            free_cash_flow = None
            if operating_cf is not None and capex is not None:
                free_cash_flow = operating_cf - capex

            cash = (
                _safe_value(balance.get("cash_and_cash_equivalents"))
                or _safe_value(balance.get("cash_and_cash_equivalents_at_carrying_value"))
            )

            total_debt = _safe_value(balance.get("total_debt")) or _safe_value(balance.get("long_term_debt"))

            # dedupe check
            exists = (
                db.query(FinancialPeriod)
                .filter(
                    FinancialPeriod.tenant_id == tenant_id,
                    FinancialPeriod.symbol == sym,
                    FinancialPeriod.period_type == detected_type,
                    FinancialPeriod.period_end == end_date,
                )
                .first()
            )
            if exists:
                continue

            row = FinancialPeriod(
                tenant_id=tenant_id,
                symbol=sym,
                period_type=detected_type,
                period_end=end_date,
                fiscal_year=fiscal_year,
                fiscal_period=fiscal_period_str if fiscal_period_str else None,
                revenue=revenue,
                gross_profit=gross_profit,
                operating_income=operating_income,
                net_income=net_income,
                eps_basic=eps_basic,
                eps_diluted=eps_diluted,
                ebitda=ebitda,
                operating_cash_flow=operating_cf,
                capex=capex,
                free_cash_flow=free_cash_flow,
                cash=cash,
                total_debt=total_debt,
            )

            db.add(row)
            inserted += 1

        db.commit()
        return inserted

    except Exception:
        db.rollback()   # FIX: keeps session usable after errors
        raise


def list_financial_periods(
    db: Session,
    tenant_id: str,
    symbol: str,
    period_type: str = "annual",
    limit: int = 20,
):
    sym = symbol.upper().strip()
    pt = (period_type or "annual").lower().strip()

    q = (
        db.query(FinancialPeriod)
        .filter(
            FinancialPeriod.tenant_id == tenant_id,
            FinancialPeriod.symbol == sym,
        )
        .order_by(FinancialPeriod.period_end.desc())
    )

    if pt in ("annual", "quarterly"):
        q = q.filter(FinancialPeriod.period_type == pt)

    return q.limit(limit).all()