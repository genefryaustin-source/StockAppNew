import yfinance as yf


def _safe_float(x):
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


def _normalize_fundamentals(f):
    if not f:
        return {}

    valuation = f.get("valuation", {}) or {}

    # ---------------------------
    # VALUATION (CRITICAL FIX)
    # ---------------------------
    f["pe_ttm"] = _safe_float(
        f.get("pe_ttm")
        or f.get("peRatioTTM")
        or f.get("trailingPE")
        or f.get("pe_ratio")
        or valuation.get("pe")
    )

    f["ps_ttm"] = _safe_float(
        f.get("ps_ttm")
        or f.get("priceToSalesTTM")
        or f.get("priceToSalesTrailing12Months")
        or f.get("ps_ratio")
        or valuation.get("ps")
    )

    f["ev_ebitda"] = _safe_float(
        f.get("ev_ebitda")
        or f.get("enterpriseToEbitda")
        or f.get("enterpriseToEbitdaRatio")
        or f.get("evToEbitda")
        or valuation.get("ev_ebitda")
    )

    # ---------------------------
    # CORE FUNDAMENTALS
    # ---------------------------
    f["revenue"] = _safe_float(
        f.get("revenue")
        or f.get("totalRevenue")
    )

    f["gross_margin"] = _safe_float(
        f.get("gross_margin")
        or f.get("grossMargins")
    )

    f["operating_margin"] = _safe_float(
        f.get("operating_margin")
        or f.get("operatingMargins")
    )

    f["fcf"] = _safe_float(
        f.get("fcf")
        or f.get("freeCashFlow")
    )

    return f


def get_fundamentals(symbol: str):
    """
    Analytics-isolated fundamentals provider.
    This is what runner should ultimately receive.
    """

    try:
        tk = yf.Ticker(symbol)

        info = {}
        try:
            info = tk.info or {}
        except Exception:
            pass

        fundamentals = {
            # raw mappings
            "peRatioTTM": info.get("trailingPE"),
            "priceToSalesTTM": info.get("priceToSalesTrailing12Months"),
            "enterpriseToEbitda": info.get("enterpriseToEbitda"),
            "totalRevenue": info.get("totalRevenue"),
            "grossMargins": info.get("grossMargins"),
            "operatingMargins": info.get("operatingMargins"),
            "freeCashFlow": info.get("freeCashFlow"),
        }

        # 🔥 CRITICAL FIX
        fundamentals = _normalize_fundamentals(fundamentals)

        # DEBUG (remove later)
        print(
            "[ANALYTICS FUNDAMENTALS]",
            symbol,
            fundamentals.get("pe_ttm"),
            fundamentals.get("ps_ttm"),
            fundamentals.get("ev_ebitda"),
        )

        return fundamentals

    except Exception as e:
        print("FUNDAMENTALS SERVICE ERROR:", e)
        return {}