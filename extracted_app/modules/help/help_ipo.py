import streamlit as st


def _section(title: str, body: str, expanded: bool = False) -> None:
    with st.expander(title, expanded=expanded):
        st.markdown(body)


def render_ipo_help():
    st.title("🏛️ IPO Intelligence Help")
    _section("IPO Intelligence overview", """
IPO Intelligence helps track public offering candidates, filings, pricing, sector themes, and post-IPO performance.

IPO research should combine SEC filings, company fundamentals, market context, sector conditions, and comparable-company valuation.
""", True)
    _section("Core workflow", """
1. Load IPO candidates.
2. Review company profile.
3. Review filing status.
4. Compare sector and peers.
5. Evaluate valuation range.
6. Track pricing, lockups, and post-IPO performance.
7. Export or report findings.
""")
    _section("Data to review", """
- S-1 or amended filing.
- Revenue growth.
- Gross margin.
- Operating losses.
- Cash burn.
- Share structure.
- Underwriters.
- Sector comparables.
- Risk factors.
""")
    _section("Common issues", """
## No IPO records
Check provider availability or manually add candidates.

## Filing data missing
Confirm SEC/EDGAR access and symbol/company identifiers.

## Valuation fields blank
Comparable-company data or financials may not have loaded yet.
""")

def render_help():
    render_ipo_help()
