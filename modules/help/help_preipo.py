# modules/help/help_preipo.py

import streamlit as st


def render_help_preipo():

    st.header("🏢 Pre-IPO Intelligence Center")

    st.markdown("""
The Pre-IPO Intelligence Center identifies companies
moving toward public offerings before IPO pricing occurs.

## SEC Discovery

Monitors:

- S-1
- S-1/A
- F-1
- F-1/A
- 424B3
- 424B4
- S-4
- SPAC filings

## IPO Probability Engine

Calculates:

- IPO Probability
- IPO Readiness
- IPO Opportunity Score
- Confidence Score

## IPO Maturity Model

Stages:

1. Early Discovery
2. Filing Stage
3. Amendment Stage
4. Prospectus Stage
5. Pricing Stage
6. Public Listing

## Pipeline Dashboard

Shows:

- Highest Probability IPOs
- Recent Filings
- Sector Breakdown
- SPAC Candidates
- Expected Timeline

## Watchlists

Track:

- Filing Updates
- IPO Probability Changes
- New Amendments
- Sector Movement
""")