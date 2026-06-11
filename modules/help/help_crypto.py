import streamlit as st


def _section(title: str, body: str, expanded: bool = False) -> None:
    with st.expander(title, expanded=expanded):
        st.markdown(body)


def render_crypto_help():
    st.title("₿ Crypto Help — Market Data, Sentiment, Analysis")
    _section("Crypto module overview", """
Crypto tools support digital asset monitoring, market data, sentiment, research notes, and risk review. Crypto behavior can differ sharply from equities, so liquidity, exchange risk, volatility, and news sensitivity should be reviewed carefully.
""", True)
    _section("Crypto workflow", """
1. Select asset or watchlist.
2. Refresh crypto data.
3. Review price/volume behavior.
4. Check sentiment/news if available.
5. Review AI summary or risk notes.
6. Export/report findings.
""")
    _section("Key risk factors", """
- High volatility.
- Weekend and 24/7 trading.
- Exchange-specific liquidity.
- Regulatory news.
- Stablecoin/depegging events.
- Wallet/exchange custody risk.
- Correlation changes with equities.
""")
    _section("Troubleshooting", """
## Crypto page fails
Check provider settings and module imports.

## Prices stale
Confirm crypto provider availability and cache status.

## Sentiment unavailable
Confirm news/sentiment provider keys and supported asset symbols.
""")

def render_help():
    render_crypto_help()
