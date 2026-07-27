import streamlit as st


def _section(title: str, body: str, expanded: bool = False) -> None:
    with st.expander(title, expanded=expanded):
        st.markdown(body)


def render_stock_research_help():
    st.title("📊 Stock Research Help — Watchlists, Universe, Market Data, Analytics, Rankings")
    _section("Research workflow overview", """
The stock research workflow is the center of the platform:

```text
Watchlists / Universe
    ↓
Market Data Refresh
    ↓
Analytics
    ↓
Rankings / Stock Dashboard / Earnings / Reports
```

The research pages are dependent on data freshness. Empty rankings, blank charts, or missing scores usually mean that market data or analytics has not been run yet.
""", True)
    _section("📋 Watchlists", """
## Purpose
Watchlists organize symbols into research groups.

## Typical uses
- Monitor names a user follows every day.
- Prepare research groups for analytics.
- Track high-conviction candidates.
- Separate client holdings, sector themes, earnings candidates, or trade ideas.

## Workflow
1. Create a watchlist.
2. Add symbols.
3. Refresh market data for the watchlist.
4. Run analytics.
5. Review rankings, stock dashboard, alerts, and reports.

## Best practices
Keep watchlists focused. Use Universe tools for broader market coverage.
""")
    _section("🌐 Universe Builder", """
## Purpose
Universe tools define the larger set of securities that the app analyzes.

## Common universe types
- Full available symbol universe.
- Sector-specific universes.
- Large-cap growth names.
- Dividend/income names.
- High-volume/liquid stocks.
- Portfolio holdings.
- Watchlist symbols.

## Why it matters
The universe determines what appears in analytics, rankings, screens, scanners, and portfolio construction.
""")
    _section("📡 Market Data Refresh", """
## Purpose
Market Data is the foundation for almost everything else.

## Provider failover order
The platform can use provider failover similar to:

```text
Polygon / Massive
    ↓
MarketData.app
    ↓
Finnhub
    ↓
Alpha Vantage
    ↓
TwelveData
    ↓
Yahoo fallback
```

## Important controls
- `Limit symbols = 0` means refresh all symbols.
- Small limits like 25, 50, or 100 are useful for testing.
- Provider health should be checked when refreshes slow down or fail.

## Feeds
Market data feeds Analytics, Rankings, AI Rankings, Stock Dashboard, Portfolio Analytics, Intraday, Alerts, Scanner, Reports, and Forecasting.
""", True)
    _section("⚙️ Analytics", """
## Purpose
Analytics converts raw data into decision inputs.

## Typical analytics outputs
- Price momentum.
- Volatility.
- Drawdown.
- Valuation scores.
- Growth scores.
- Quality scores.
- Technical indicators.
- Composite scores.
- Risk metrics.

## Dependency rule
Run market data first, then analytics. Rankings and portfolio tools are only as good as the latest analytics run.
""", True)
    _section("🏆 Rankings and AI Ranking Engine", """
## Purpose
Rankings prioritize names from the universe.

## Ranking dimensions
- Value.
- Growth.
- Quality.
- Momentum.
- Risk-adjusted metrics.
- Composite score.
- AI-adjusted confidence.

## How to use rankings
Use rankings as a discovery tool, then open Stock Dashboard, Earnings, Sentiment, Forecasting, and Reports before making decisions.
""")
    _section("📈 Stock Dashboard", """
## Purpose
Single-stock research workspace.

## Useful views
- Price history.
- Technical indicators.
- Fundamentals.
- Analytics summary.
- Earnings/events.
- Sentiment.
- Forecasts.
- Rankings context.

## Best workflow
Use Stock Dashboard after a name appears in Rankings, Screener, Alerts, Scanner, or Options Flow.
""")
    _section("🔍 Screener and Formula Builder", """
## Purpose
Filter stocks using structured rules and formulas.

## Common filters
Price, market cap, volume, sector, valuation, growth, momentum, RSI, technical setup, risk, and composite score.

## Workflow
1. Select universe or watchlist.
2. Set filters or formula.
3. Run screen.
4. Save candidates to watchlist or portfolio workflow.
5. Review rankings and Stock Dashboard.
""")

# aliases
def render_help():
    render_stock_research_help()
