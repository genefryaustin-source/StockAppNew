# modules/help/help_options.py

import streamlit as st


def render_help_options():

    st.header("🧩 Options Strategy Center")

    st.markdown("""
Options tools support income, hedging, and strategy construction.

## Covered Call Manager

Generate covered call opportunities.

## Cash Secured Put Manager

Identify premium income opportunities.

## Wheel Strategy Manager

Manage complete wheel workflows.

## Vertical Spread Builder

Analyze:

- Bull Call Spreads
- Bear Put Spreads

## Iron Condor Builder

Build neutral premium strategies.

## Butterfly Builder

Construct defined-risk volatility strategies.

## Greeks Dashboard

Monitor:

- Delta
- Gamma
- Theta
- Vega
- Rho

## Risk Dashboard

Track:

- Position Exposure
- Strategy Exposure
- Portfolio Greeks
""")