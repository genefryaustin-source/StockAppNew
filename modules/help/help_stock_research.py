import streamlit as st

def render_help_stock_research():

    st.header("📊 Stock Research")

    st.markdown("""
### Core Research Tools

- Dashboard
- Watchlists
- Screeners
- Analytics
- Rankings
- Earnings
- Transcripts
- AI Research

### Market Data

Provider Failover:

1. Polygon
2. MarketData.app
3. Finnhub
4. Alpha Vantage
5. TwelveData
6. Yahoo

### News

Uses:

- Finnhub
- Polygon
- Alpha Vantage News Sentiment
- Cached News
""")