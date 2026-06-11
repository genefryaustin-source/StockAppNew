import streamlit as st


def _section(title: str, body: str, expanded: bool = False) -> None:
    with st.expander(title, expanded=expanded):
        st.markdown(body)


def render_portfolio_help():
    st.title("💼 Portfolio Help — Construction, Analytics, Trading, Reports")
    _section("Portfolio workflow", """
Portfolio workflows convert ranked ideas into monitored allocations:

```text
Rankings / Signals
    ↓
Portfolio Construction
    ↓
Portfolio Deployment / Trading
    ↓
Portfolio Analytics / Risk / Reports
```
""", True)
    _section("🏗️ Portfolio Construction", """
## Purpose
Builds portfolios from ranked candidates.

## Controls
- Portfolio size.
- Max/min position weight.
- Sector caps.
- Cash reserve.
- Ranking basis.
- Risk or volatility constraints.

## Best practice
Do not construct portfolios from stale rankings. Refresh data and analytics first.
""")
    _section("📊 Portfolio Analytics", """
## Purpose
Monitors holdings, cash, risk, NAV, PnL, drift, and exposure.

## Questions it answers
- Is the portfolio concentrated?
- Has sector exposure drifted?
- Are holdings still ranked well?
- Has volatility increased?
- Are replacement candidates available?
""", True)
    _section("🤖 AI Portfolio Center", """
## Purpose
Adds higher-level portfolio review and decision support.

## Possible uses
- Risk review.
- Allocation review.
- Replacement suggestions.
- Holdings explanation.
- Portfolio summary.
- Rebalancing context.

AI Portfolio should support human review, not replace investment judgment.
""")
    _section("💸 Trading / Deployment", """
## Purpose
Supports portfolio deployment and trade workflow.

## Typical functions
- Paper trading.
- Buy/sell workflow.
- Order sizing.
- Cash tracking.
- Position tracking.
- Deployment from model portfolios.

Always confirm whether the app is running in paper/simulated mode or connected to live execution.
""")
    _section("📄 Portfolio Reports", """
## Purpose
Creates portfolio summaries for internal review, client reporting, or investment committee workflows.

Reports should be generated after data and analytics are current.
""")
    _section("Troubleshooting portfolio issues", """
## Portfolio empty
Check whether a portfolio exists, holdings were imported, and user/tenant assignment is correct.

## PnL missing
Confirm latest prices exist and market data refreshed.

## Construction output empty
Confirm rankings are populated and analytics are current.

## Unauthorized role
Confirm user role is `client`, `tenant_admin`, or `super_admin` as required by the Portfolio route.
""")

# aliases
def render_help():
    render_portfolio_help()
