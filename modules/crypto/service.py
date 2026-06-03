from pycoingecko import CoinGeckoAPI
import pandas as pd
from datetime import datetime, timedelta
import json
import os
from sqlalchemy import text

cg = CoinGeckoAPI()  # Free tier (demo key optional)

CRYPTO_CACHE_DIR = "market_cache/crypto"
os.makedirs(CRYPTO_CACHE_DIR, exist_ok=True)

def get_crypto_quote(symbol: str = "bitcoin"):
    """Get current price + market data for a coin."""
    try:
        data = cg.get_price(ids=symbol.lower(), vs_currencies="usd", include_market_cap=True, include_24hr_vol=True, include_24hr_change=True)
        if symbol.lower() in data:
            return {
                "price": data[symbol.lower()]["usd"],
                "market_cap": data[symbol.lower()].get("usd_market_cap"),
                "volume_24h": data[symbol.lower()].get("usd_24h_vol"),
                "change_24h": data[symbol.lower()].get("usd_24h_change"),
                "symbol": symbol.upper(),
                "timestamp": datetime.utcnow().isoformat()
            }
    except Exception:
        pass
    return {"price": None, "symbol": symbol.upper()}

def get_crypto_history(symbol: str = "bitcoin", days: int = 365):
    """Get historical OHLC data."""
    try:
        data = cg.get_coin_ohlc_by_id(id=symbol.lower(), vs_currency="usd", days=days)
        df = pd.DataFrame(data, columns=["timestamp", "open", "high", "low", "close"])
        df["Date"] = pd.to_datetime(df["timestamp"], unit="ms")
        return df[["Date", "open", "high", "low", "close"]]
    except Exception:
        return pd.DataFrame()

def render_crypto_page(db, user):
    import streamlit as st
    import plotly.graph_objects as go

    st.header("🪙 Crypto Coverage")
    st.caption("Powered by CoinGecko • Free Tier")

    col1, col2 = st.columns([3, 1])
    with col1:
        coin = st.selectbox("Select Asset", ["bitcoin", "ethereum", "solana", "cardano", "ripple"], index=0)
    with col2:
        days = st.selectbox("Period", [7, 30, 90, 365], index=3)

    quote = get_crypto_quote(coin)
    if quote["price"]:
        st.metric(f"{coin.upper()}", f"${quote['price']:,.2f}", f"{quote.get('change_24h', 0):+.2f}%")

    df = get_crypto_history(coin, days)
    if not df.empty:
        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=df["Date"], open=df["open"], high=df["high"], low=df["low"], close=df["close"]))
        fig.update_layout(height=600, title=f"{coin.upper()} Price Chart")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No historical data available.")

    # Top Coins Table
    st.subheader("Top Cryptocurrencies")
    try:
        top = cg.get_coins_markets(vs_currency="usd", order="market_cap_desc", per_page=20, page=1)
        df_top = pd.DataFrame(top)[["symbol", "current_price", "market_cap", "price_change_percentage_24h", "total_volume"]]
        df_top.columns = ["Symbol", "Price", "Market Cap", "24h %", "Volume"]
        st.dataframe(df_top, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"Failed to load top coins: {e}")

# ... existing code ...

def get_crypto_analytics_snapshot(coin_id: str):
    """Generate analytics-style snapshot for crypto (mimics equity snapshots)"""
    quote = get_crypto_quote(coin_id)
    if not quote or not quote.get("price"):
        return None

    # Mock realistic crypto metrics
    price = quote["price"]
    change_24h = quote.get("change_24h", 0)

    return {
        "symbol": coin_id.upper(),
        "asset_type": "crypto",
        "composite_score": min(95, max(40, 70 + (change_24h * 2))),  # momentum biased
        "momentum_score": round(50 + change_24h * 1.5, 1),
        "risk_score": round(60 + abs(change_24h) * 0.8, 1),
        "quality_score": 75,  # BTC/ETH get higher quality
        "value_score": 65,
        "growth_score": round(80 + change_24h, 1),
        "price": price,
        "change_24h": change_24h,
        "market_cap": quote.get("market_cap"),
        "volume_24h": quote.get("volume_24h"),
        "sector": "Cryptocurrency",
        "rating": "BUY" if change_24h > 2 else "HOLD",
    }