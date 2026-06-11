# modules/help/help_admin.py

import streamlit as st


def render_help_admin():

    st.header("🛠 Administration")

    st.markdown("""
Administration tools manage platform operations.

## User Management

- Create Users
- Disable Users
- Assign Roles

## Tenant Management

- Create Tenants
- Manage Access
- Configure Features

## Provider Management

Monitor:

- Polygon
- MarketData
- Finnhub
- Alpha Vantage
- TwelveData
- Yahoo

## Runtime Monitoring

Track:

- Refresh Jobs
- Analytics Jobs
- Queue Status
- Failures

## Health Monitoring

Review:

- Diagnostics
- Self Healing
- Validation Results
""")