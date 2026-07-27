from sqlalchemy import text
from modules.universe.etf_set import ETF_SET


def classify_symbol(symbol: str, db=None) -> dict:
    symbol = symbol.upper().strip()

    # -----------------------------
    # ETF DETECTION (STRONG)
    # -----------------------------
    ETF_HINTS = ["ETF", "FUND", "TRUST"]

    if symbol in {"SPY","QQQ","IWM","DIA","ARKK","XLF","XLE","XLK"}:
        return {"exchange": "AMEX", "is_etf": True}

    if len(symbol) <= 5 and symbol.endswith(("X","Y")):
        return {"exchange": "AMEX", "is_etf": True}

    # -----------------------------
    # STRUCTURAL EXCHANGE RULES
    # -----------------------------

    # NYSE patterns
    if "." in symbol:
        return {"exchange": "NYSE", "is_etf": False}

    # 5-letter = NASDAQ (very common rule)
    if len(symbol) == 5:
        return {"exchange": "NASDAQ", "is_etf": False}

    # 1–4 letters → split logic
    if len(symbol) <= 4:

        # crude but effective distribution
        if symbol[0] < "M":
            return {"exchange": "NASDAQ", "is_etf": False}
        else:
            return {"exchange": "NYSE", "is_etf": False}

    # fallback
    return {"exchange": "NASDAQ", "is_etf": False}