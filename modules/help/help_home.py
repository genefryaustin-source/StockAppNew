import streamlit as st

def render_help_home():

    st.title("📘 Stock Research Terminal Help Center")

    st.markdown("""
Welcome to the Conduro Ventures Stock Research Terminal.

Use the Help navigation in the sidebar to access detailed documentation for:

- Stock Research
- Portfolio Management
- Options Intelligence
- IPO Intelligence
- Pre-IPO Intelligence
- AI Modules
- Crypto Analytics
- Administration
- Analytics Fabric
- API Providers
- Troubleshooting
""")

    st.success(
        "Recommended workflow: Market Data → Analytics → Rankings → Portfolio → Reports"
    )