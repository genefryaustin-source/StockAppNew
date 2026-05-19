import os
import requests


BASE_URL = "https://financialmodelingprep.com/api/v3"


# --------------------------------------------------
# API KEY
# --------------------------------------------------

def _get_key():
    key = os.getenv("FMP_API_KEY")
    if not key:
        raise Exception("Missing FMP_API_KEY")
    return key


# --------------------------------------------------
# HTTP CLIENT
# --------------------------------------------------

def fmp_get(path, params=None):
    params = params or {}
    params["apikey"] = _get_key()

    url = f"{BASE_URL}/{path}"

    r = requests.get(url, params=params, timeout=20)

    if r.status_code != 200:
        raise Exception(f"FMP error {r.status_code}: {r.text}")

    return r.json()


# --------------------------------------------------
# SYMBOL NORMALIZATION
# --------------------------------------------------

def _normalize_symbol(symbol: str) -> str:
    # BRK.B → BRK-B (FMP compatibility)
    return symbol.replace(".", "-")


# --------------------------------------------------
# FCF COMPUTATION (ROBUST)
# --------------------------------------------------

def _compute_fcf_and_margin(revenue, raw_fcf, cfo, capex, gross_margin, operating_margin):
    """
    Multi-layer FCF calculation with fallbacks
    """

    # ---------------------------------
    # 1. Direct FCF (best)
    # ---------------------------------
    if raw_fcf is not None and revenue:
        try:
            return float(raw_fcf), float(raw_fcf) / float(revenue)
        except Exception:
            pass

    # ---------------------------------
    # 2. CFO - CapEx fallback
    # ---------------------------------
    if cfo is not None and capex is not None:
        try:
            fcf = float(cfo) - abs(float(capex))
            if revenue:
                return fcf, fcf / float(revenue)
            return fcf, None
        except Exception:
            pass

    # ---------------------------------
    # 3. Margin proxy fallback
    # ---------------------------------
    if gross_margin is not None and operating_margin is not None:
        try:
            proxy_margin = float(gross_margin) * float(operating_margin)
            if revenue:
                return proxy_margin * float(revenue), proxy_margin
            return None, proxy_margin
        except Exception:
            pass

    # ---------------------------------
    # 4. No data
    # ---------------------------------
    return None, None


# --------------------------------------------------
# MAIN FUNCTION
# --------------------------------------------------

def get_fmp_fundamentals(symbol):
    try:
        symbol = _normalize_symbol(symbol)

        profile = fmp_get(f"profile/{symbol}")
        ratios = fmp_get(f"ratios-ttm/{symbol}")
        key_metrics = fmp_get(f"key-metrics-ttm/{symbol}")
        income = fmp_get(f"income-statement/{symbol}", {"limit": 5})
        cashflow = fmp_get(f"cash-flow-statement/{symbol}", {"limit": 5})

        profile = profile[0] if profile else {}
        ratios = ratios[0] if ratios else {}
        key_metrics = key_metrics[0] if key_metrics else {}

        # --------------------------------------------------
        # REVENUE SERIES
        # --------------------------------------------------

        revenues = []
        for row in income:
            val = row.get("revenue")
            if val:
                try:
                    revenues.append(float(val))
                except Exception:
                    continue

        revenues = list(reversed(revenues))
        revenue_latest = revenues[-1] if revenues else None

        # --------------------------------------------------
        # MARGINS
        # --------------------------------------------------

        gross_margin = ratios.get("grossProfitMarginTTM")
        operating_margin = ratios.get("operatingProfitMarginTTM")

        # --------------------------------------------------
        # CASHFLOW
        # --------------------------------------------------

        raw_fcf = None
        cfo = None
        capex = None

        if cashflow:
            latest_cf = cashflow[0]

            raw_fcf = latest_cf.get("freeCashFlow")
            cfo = latest_cf.get("operatingCashFlow")
            capex = latest_cf.get("capitalExpenditure")

        fcf, fcf_margin = _compute_fcf_and_margin(
            revenue=revenue_latest,
            raw_fcf=raw_fcf,
            cfo=cfo,
            capex=capex,
            gross_margin=gross_margin,
            operating_margin=operating_margin,
        )

        # --------------------------------------------------
        # RETURN OBJECT
        # --------------------------------------------------

        return {
            "revenue": revenues,
            "gross_margin": gross_margin,
            "operating_margin": operating_margin,
            "fcf": fcf,
            "fcf_margin": fcf_margin,
            "pe_ttm": ratios.get("priceEarningsRatioTTM"),
            "ps_ttm": ratios.get("priceToSalesRatioTTM"),
            "ev_ebitda": key_metrics.get("enterpriseValueOverEBITDATTM"),
            "sector": profile.get("sector"),
        }

    except Exception as e:
        print("FMP ERROR:", symbol, e)
        return {}