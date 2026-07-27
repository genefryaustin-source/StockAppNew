# valuation.py for Analytics
from sqlalchemy.orm import Session
from modules.institutional.fundamentals import latest_snapshot


def compute_valuation(db: Session, tenant_id: str, symbol: str):

    snap = latest_snapshot(db, tenant_id, symbol, max_age_hours=9999)

    if not snap:
        return {
            "pe_ttm": None,
            "ps_ttm": None,
            "ev_ebitda": None
        }

    market_cap = snap.market_cap
    revenue = snap.revenue_ttm
    net_income = getattr(snap, "net_income", None)
    ebitda = getattr(snap, "ebitda", None)
    cash = getattr(snap, "cash", None)
    debt = getattr(snap, "total_debt", None)

    pe = None
    ps = None
    ev_ebitda = None

    # -----------------------------
    # P/E
    # -----------------------------

    if market_cap and net_income and net_income > 0:
        pe = market_cap / net_income

    # -----------------------------
    # P/S
    # -----------------------------

    if market_cap and revenue and revenue > 0:
        ps = market_cap / revenue

    # -----------------------------
    # EV / EBITDA
    # -----------------------------

    if market_cap and ebitda and ebitda > 0:

        enterprise_value = market_cap

        if debt:
            enterprise_value += debt

        if cash:
            enterprise_value -= cash

        ev_ebitda = enterprise_value / ebitda

    return {
        "pe_ttm": pe,
        "ps_ttm": ps,
        "ev_ebitda": ev_ebitda
    }