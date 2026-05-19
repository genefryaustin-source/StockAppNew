# financial_metrics.py in Analytics
from math import pow

def _cagr(start, end, years):
    if start is None or end is None or start <= 0 or years <= 0:
        return None
    return pow(end / start, 1 / years) - 1

def compute_financial_metrics(db, tenant_id: str, symbol: str):
    """
    Returns dict with revenue CAGR + margins if available.
    """
    sym = symbol.upper()

    # Try to read FundamentalSnapshot (institutional table)
    try:
        from modules.institutional.models import FundamentalSnapshot
        rows = (db.query(FundamentalSnapshot)
                  .filter(FundamentalSnapshot.tenant_id == tenant_id,
                          FundamentalSnapshot.symbol == sym)
                  .order_by(FundamentalSnapshot.asof.desc())
                  .limit(8)
                  .all())
    except Exception:
        rows = []

    if not rows:
        return {
            "revenue_cagr_3y": None,
            "gross_margin": None,
            "op_margin": None,
            "fcf_margin": None,
        }

    # Use latest snapshot for margins (if present)
    latest = rows[0]
    revenue = getattr(latest, "revenue_ttm", None)
    gross_margin = getattr(latest, "gross_margin", None)
    op_margin = getattr(latest, "op_margin", None)
    fcf_margin = getattr(latest, "fcf_margin", None)

    # CAGR requires time series; if you store revenue by asof, do simple approx
    # Use oldest within ~3y if present
    # (This is safe + deterministic; later we’ll replace with true annual series.)
    rev_3y_ago = None
    if len(rows) >= 4:
        rev_3y_ago = getattr(rows[-1], "revenue_ttm", None)

    revenue_cagr_3y = _cagr(rev_3y_ago, revenue, 3) if rev_3y_ago and revenue else None

    return {
        "revenue_cagr_3y": revenue_cagr_3y,
        "gross_margin": gross_margin,
        "op_margin": op_margin,
        "fcf_margin": fcf_margin,
    }