import streamlit as st

from modules.utils.config import get_secret


def md_secrets() -> dict:
    # Try streamlit secrets first (dev)
    try:
        s = st.secrets.get("market_data", {})
    except Exception:
        s = {}

    offline_val = s.get("ENABLE_OFFLINE_MODE")
    if offline_val is None:
        offline_val = get_secret("ENABLE_OFFLINE_MODE", False)

    return {
        "primary": s.get("PRIMARY_PROVIDER") or get_secret("PRIMARY_PROVIDER", "polygon"),
        "fallbacks": list(s.get("FALLBACK_ORDER") or ["fmp", "yahoo"]),
        "timeout": int(s.get("TIMEOUT_SECONDS") or get_secret("TIMEOUT_SECONDS", 15)),
        "max_retries": int(s.get("MAX_RETRIES") or get_secret("MAX_RETRIES", 4)),
        "ttl": int(s.get("CACHE_TTL_SECONDS") or get_secret("CACHE_TTL_SECONDS", 900)),
        "offline": str(offline_val).lower() == "true",
        "finnhub_key": s.get("FINNHUB_API_KEY") or get_secret("FINNHUB_API_KEY"),
        "eodhd_key": s.get("EODHD_API_KEY") or get_secret("EODHD_API_KEY"),
        "polygon_key": s.get("POLYGON_API_KEY") or get_secret("POLYGON_API_KEY"),
        "twelvedata_key": s.get("TWELVEDATA_API_KEY") or get_secret("TWELVEDATA_API_KEY"),
        "fmp_key": s.get("FMP_API_KEY") or get_secret("FMP_API_KEY"),
        "iex_token": s.get("IEX_API_TOKEN") or get_secret("IEX_API_TOKEN"),
        "auto_trade": get_secret("AUTO_TRADE_ENABLED", True),
        "alpaca_key": s.get("ALPACA_API_KEY") or get_secret("ALPACA_API_KEY"),
        "alpaca_secret": s.get("ALPACA_API_SECRET") or get_secret("ALPACA_API_SECRET"),
        "alpaca_base": s.get("ALPACA_BASE_URL") or get_secret("ALPACA_BASE_URL", "https://paper-api.alpaca.markets"),
    }

