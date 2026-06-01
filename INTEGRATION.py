"""
HOW TO INTEGRATE INTO app.py
════════════════════════════════════════════════════════════════

STEP 1 — Add "AI Forecast" to the pages list (section 15 of app.py)
─────────────────────────────────────────────────────────────────────
Find the `pages = [...]` list (the one for non-client roles) and
add "AI Forecast" anywhere you want it in the sidebar:

    pages = [
        "Dashboard", "Watchlists", "Screener", "Earnings", "Market Data",
        "Analytics", "Rankings", "Universe", "Stock Dashboard", "Portfolio",
        "Portfolio Construction", "Portfolio Deployment", "Market Overview",
        "AI Rankings", "Strategy Lab", "Regime Engine", "Strategy Discovery",
        "Strategy Library", "Alerts", "Admin", "AI Portfolio",
        "AI Forecast",   # ← ADD THIS LINE
        "Help"
    ]


STEP 2 — Add the page handler (at the end of the routing block)
─────────────────────────────────────────────────────────────────
Add this block just before the "elif page == 'Help':" block:

    elif page == "AI Forecast":
        try:
            from modules.forecasting.forecast_ui import render_forecast_page
            render_forecast_page(db, user)
        except Exception as e:
            st.error("AI Forecast module failed to load.")
            st.exception(e)


STEP 3 — (Optional) Embed in Stock Dashboard
─────────────────────────────────────────────
To add the forecast directly inside the existing Stock Dashboard,
open modules/institutional/ui/stock_dashboard_ui.py and add
at the end of render_stock_dashboard(), after the news section:

    # ── AI Forecast, Congress Trades & Institutional Flow ──
    st.divider()
    try:
        from modules.forecasting.forecast_ui import (
            render_forecast_panel,
            render_congress_panel,
            render_institutional_panel,
        )
        tab_fc, tab_cong, tab_inst = st.tabs([
            "🤖 AI Forecast", "🏛️ Congress Trades", "🏦 Institutional Flow"
        ])
        with tab_fc:
            render_forecast_panel(db, user, symbol)
        with tab_cong:
            render_congress_panel(symbol)
        with tab_inst:
            render_institutional_panel(symbol)
    except Exception as e:
        st.warning(f"Market intelligence panels unavailable: {e}")


STEP 4 — Install new dependencies
──────────────────────────────────
Add to requirements.txt:

    anthropic>=0.30.0
    requests>=2.31.0

Then run:  pip install anthropic requests

(yfinance and matplotlib are already in your project)


STEP 5 — Set environment variables / Streamlit secrets
────────────────────────────────────────────────────────
Required for AI forecasts:
    ANTHROPIC_API_KEY = "sk-ant-..."

Optional for richer Congress data:
    QUIVER_API_KEY = "..."        # quiverquant.com — $20/mo plan

Optional for 13F institutional data:
    FINTEL_API_KEY = "..."        # fintel.io

In Streamlit Cloud, add these under Settings → Secrets as TOML:
    ANTHROPIC_API_KEY = "sk-ant-..."
    QUIVER_API_KEY    = "..."

In .streamlit/secrets.toml for local dev:
    ANTHROPIC_API_KEY = "sk-ant-..."


FALLBACK BEHAVIOUR (no API keys needed to run)
───────────────────────────────────────────────
• No ANTHROPIC_API_KEY → statistical drift+volatility forecast shown
  with a warning banner. All UI still works.

• No QUIVER_API_KEY → falls back to House Stock Watcher free JSON
  (House members only, updated daily, no Senate data).

• No FINTEL_API_KEY → falls back to yfinance institutional_holders
  (free, always available, slightly less detail).


FILE PLACEMENT
──────────────
Place these three files into your project at:

    modules/forecasting/__init__.py         (empty)
    modules/forecasting/forecast_engine.py  (AI forecast via Anthropic)
    modules/forecasting/congress_service.py (Congress trades)
    modules/forecasting/institutional_service.py (13F data)
    modules/forecasting/forecast_ui.py      (Streamlit UI — all 3 panels)
"""
