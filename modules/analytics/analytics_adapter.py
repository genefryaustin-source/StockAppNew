# modules/analytics/analytics_adapter.py

def _safe_float(x):
    try:
        return float(x)
    except:
        return None


def normalize_fundamentals_for_analytics(f):
    """
    Ensures Analytics module is fully isolated and receives
    canonical fields required by runner.py
    """

    if not f:
        return {}

    valuation = f.get("valuation", {})

    return {
        **f,

        # --- Canonical valuation fields ---
        "pe_ttm": _safe_float(
            f.get("pe_ttm")
            or f.get("peRatioTTM")
            or f.get("pe_ratio")
            or valuation.get("pe")
        ),

        "ps_ttm": _safe_float(
            f.get("ps_ttm")
            or f.get("priceToSalesTTM")
            or f.get("ps_ratio")
            or valuation.get("ps")
        ),

        "ev_ebitda": _safe_float(
            f.get("ev_ebitda")
            or f.get("enterpriseToEbitda")
            or f.get("evToEbitda")
            or valuation.get("ev_ebitda")
        ),
    }