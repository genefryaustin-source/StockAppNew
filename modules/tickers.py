import re
import requests

YF_SEARCH = "https://query1.finance.yahoo.com/v1/finance/search"

def is_ticker_like(s: str) -> bool:
    s = s.strip().upper()
    return bool(re.fullmatch(r"[A-Z\.\-]{1,8}", s))

def resolve_symbol(query: str) -> tuple[str, str]:
    """
    Resolve user input as ticker or company name.
    If ticker-like, return directly.
    Else use Yahoo Finance search endpoint.
    """
    q = (query or "").strip()
    if not q:
        return "PLTR", "Empty input; defaulted to PLTR."

    if is_ticker_like(q):
        return q.upper(), ""

    # Use Yahoo Finance search to resolve name -> ticker
    try:
        r = requests.get(YF_SEARCH, params={"q": q, "quotesCount": 1, "newsCount": 0}, timeout=10)
        r.raise_for_status()
        data = r.json()
        quotes = data.get("quotes", [])
        if quotes:
            sym = quotes[0].get("symbol")
            longname = quotes[0].get("longname") or quotes[0].get("shortname")
            note = f"Resolved via Yahoo search: {longname} → {sym}"
            return sym, note
    except Exception as e:
        return "PLTR", f"Search failed ({e}); defaulted to PLTR."

    return "PLTR", "No match found; defaulted to PLTR."