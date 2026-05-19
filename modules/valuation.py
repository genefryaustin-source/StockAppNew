from sqlalchemy.orm import Session
from modules.institutional.fundamentals import latest_snapshot


def compute_valuation(db: Session, tenant_id: str, symbol: str):
    """
    Phase A valuation:
      - P/S = market_cap / revenue_ttm (if both exist)
    Phase B valuation fields (P/E, EV/EBITDA) remain None until we ingest EV/EPS/EBITDA inputs.
    """
    sym = symbol.upper()
    snap = latest_snapshot(db, tenant_id, sym, max_age_hours=72)

    if not snap:
        return {"pe_ttm": None, "ps_ttm": None, "ev_ebitda": None}

    market_cap = getattr(snap, "market_cap", None)
    revenue_ttm = getattr(snap, "revenue_ttm", None)

    ps_ttm = None
    if market_cap is not None and revenue_ttm is not None:
        try:
            if float(revenue_ttm) > 0:
                ps_ttm = float(market_cap) / float(revenue_ttm)
        except Exception:
            ps_ttm = None

    return {
        "pe_ttm": getattr(snap, "pe_ttm", None),
        "ps_ttm": ps_ttm,
        "ev_ebitda": None,
    }