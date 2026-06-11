# modules/help/help_ipo.py

import streamlit as st


def render_help_ipo():

    st.header("🚀 IPO Intelligence Center")

    st.markdown("""
The IPO Intelligence Center tracks public offerings from
announcement through listing.

## Modules

### Upcoming IPOs

Provides:

- IPO Calendar
- Deal Size
- Exchange
- Expected Pricing Date
- Lead Underwriters

### IPO Watchlist

Track IPOs of interest.

Monitor:

- Status
- Pricing Updates
- Filing Changes
- Listing Dates

### IPO Analytics

Analyze:

- Average Deal Size
- Sector Activity
- Exchange Activity
- Underwriter Trends

### IPO Opportunity Analysis

Identify:

- Large offerings
- Fast-growing sectors
- High demand deals
- Potential institutional interest

### Daily Workflow

1. Refresh IPO Calendar
2. Review New Offerings
3. Analyze Sector Trends
4. Update Watchlists
5. Generate IPO Reports
""")