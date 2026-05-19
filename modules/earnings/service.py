# service.py in Earnings
import requests
import streamlit as st

def get_earnings(symbol):

    key = st.secrets["market_data"]["POLYGON_API_KEY"]

    url = f"https://api.polygon.io/vX/reference/earnings?ticker={symbol}"

    r = requests.get(
        url,
        params={"apiKey": key},
    )

    return r.json()