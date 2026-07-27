import streamlit as st


def _section(title: str, body: str, expanded: bool = False) -> None:
    with st.expander(title, expanded=expanded):
        st.markdown(body)


def render_preipo_help():
    st.title("🧭 Pre-IPO Intelligence Help")
    _section("Pre-IPO overview", """
Pre-IPO Intelligence tracks private companies, potential IPO candidates, filing signals, fundraising events, sector momentum, and readiness scoring.

This module is designed to help users identify companies before they become public-market opportunities.
""", True)
    _section("Pre-IPO workflow", """
1. Add or load private company candidates.
2. Review company profile and sector.
3. Track filing signals and SEC activity where available.
4. Score IPO readiness.
5. Monitor fundraising, hiring, revenue signals, and news.
6. Compare to public comps.
7. Generate research outputs.
""")
    _section("Readiness scoring", """
Typical scoring inputs can include:
- Revenue scale.
- Growth profile.
- Profitability path.
- Market timing.
- Sector demand.
- Funding stage.
- Filing activity.
- Brand or customer traction.
- Comparable-company valuation environment.
""")
    _section("Manual provider workflow", """
Use manual provider tools when structured pre-IPO data is unavailable. Capture source, date, company name, sector, funding stage, valuation estimate, and evidence notes.
""")
    _section("Troubleshooting", """
## Pre-IPO page not shown
Ensure `Pre-IPO Intelligence` exists in the app page list.

## Candidate has no score
Confirm required fields exist in the model or scoring service.

## SEC data empty
Private companies may not have public filings yet.
""")

def render_help():
    render_preipo_help()
