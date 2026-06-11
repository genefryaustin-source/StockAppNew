# modules/help/help_api_providers.py

import streamlit as st


def render_help_api_providers():

    st.header("🔌 API Providers")

    st.markdown("""
## Market Data

Provider failover order:

1. Polygon / Massive
2. MarketData.app
3. Finnhub
4. Alpha Vantage
5. TwelveData
6. Yahoo

## News

- Finnhub
- Yahoo
- Provider Aggregation

## Earnings

- ROIC
- Transcript Cache

## AI

- OpenAI
- Anthropic

## SEC

- EDGAR
- Filing Discovery

## Crypto

- CoinGecko
- Fear & Greed
- Market Statistics
""")