import streamlit as st


def _section(title: str, body: str, expanded: bool = False) -> None:
    with st.expander(title, expanded=expanded):
        st.markdown(body)


def render_help_center():
    st.title("📘 StockApp / Equities Research Terminal — Help Center")
    st.markdown("""
Welcome to the StockApp Equities Research Terminal help center.

This help system is designed as an operating manual, not just a list of page descriptions. The platform works best when users follow the full workflow:

```text
Symbols / Universe
    ↓
Market Data Refresh
    ↓
Analytics Pipeline
    ↓
Rankings / Research / Signals
    ↓
Portfolio / Trading / Reports
```

If a page looks empty, the most common reason is that an earlier dependency has not been completed yet, usually market data, analytics, or universe selection.
""")
    _section("🚀 Start Here — First-Time Setup", """
## Goal
Get the app ready so a user can research stocks, review rankings, monitor portfolios, and use daily dashboards.

## Step-by-step setup

### 1. Log in and confirm your workspace
Confirm that you are in the correct tenant and role. Available pages may differ for regular users, analysts, traders, tenant admins, and super admins.

### 2. Confirm provider/API keys
The platform can rely on market data, transcript data, AI models, news, and sentiment providers. Common secrets include:

```text
POLYGON_API_KEY
MARKETDATA_API_KEY
FINNHUB_API_KEY
ALPHAVANTAGE_API_KEY
TWELVEDATA_API_KEY
OPENAI_API_KEY
ANTHROPIC_API_KEY
ROIC_API_KEY
DATABASE_URL
```

Local deployments usually use `.streamlit/secrets.toml`. Streamlit Cloud uses App → Settings → Secrets.

### 3. Create watchlists
Start with the Watchlists page and add the tickers you care about, such as AAPL, MSFT, NVDA, AMD, AMZN, META, GOOGL, PLTR.

### 4. Build or select a universe
Use Universe tools for broader coverage: sector groups, custom lists, liquidity filters, portfolio holdings, and tracked research universes.

### 5. Run Market Data Refresh
Run Market Data Refresh before analytics. Use `Limit symbols = 0` for all symbols, or a small number for testing.

### 6. Run Analytics
Analytics creates valuation, momentum, quality, growth, risk, technical, and composite scores.

### 7. Review Rankings
Use Rankings and AI Ranking Engine to find strong opportunities by value, growth, quality, momentum, composite score, confidence, and risk.

### 8. Build or monitor portfolios
Use Portfolio Construction, Portfolio Analytics, AI Portfolio, Reports, and Export.
""", True)
    _section("📅 Daily Operating Workflow", """
## Morning workflow
1. Open Market Overview for broad market context.
2. Refresh market data.
3. Run analytics.
4. Review Rankings and AI Rankings.
5. Check Alerts, Scanner, Options Flow, and Sentiment.
6. Review portfolio exposures, PnL, cash, and risk.

## During market hours
Use Intraday Charts, Options Flow, Scanner, Alerts, Market Dashboard, and Portfolio pages for tactical monitoring.

## End-of-day workflow
1. Refresh prices after market close.
2. Run analytics again.
3. Review portfolio drift and risk.
4. Generate reports.
5. Export data if needed.
6. Prepare next-day watchlist and trade candidates.
""", True)
    _section("👤 Role-Based Workflows", """
## Regular Research User
Maintain watchlists, refresh market data, run analytics, review rankings, open Stock Dashboard pages, monitor alerts, and export/report findings.

## Analyst
Build focused universes, review earnings/transcripts, use AI Q&A, compare companies, document thesis points, and generate research reports.

## Trader
Focus on intraday charts, scanner results, options flow, alerts, sentiment, rankings confirmation, and trade/risk monitoring.

## Portfolio Manager
Review holdings, cash, PnL, risk, sector drift, replacement candidates, portfolio construction, and client reports.

## Tenant Admin / Super Admin
Manage users, tenants, provider keys, platform health, analytics operations, cache problems, and deployment issues.
""")
    _section("🧭 Help Sections", """
Use the sidebar Help navigation to open detailed manuals for:

- Stock Research
- Portfolio Management
- Options Intelligence
- IPO / Pre-IPO Intelligence
- AI Modules
- Crypto
- Admin
- Analytics Fabric
- API Providers
- Troubleshooting
""")
    _section("✅ Recommended Operating Rules", """
1. Always refresh market data before analytics.
2. Always run analytics before rankings.
3. Use small symbol limits when testing provider changes.
4. Use full refresh only after provider failover is verified.
5. Use rankings as a starting point, not the only decision.
6. Use transcript AI for management commentary and risk review, not guaranteed forecasts.
7. Use options flow and sentiment as confirmation signals.
8. Export reports only after data and analytics are current.
9. Check provider health if refresh slows or fails.
10. Check Git status from the repository root before pushing updates.
""")

# backwards-compatible alias
def render_help_home():
    render_help_center()
