import streamlit as st
import os
import sys
from datetime import datetime

# Force show errors
st.set_page_config(page_title="Diagnostic", layout="wide")

st.title("🛠️ Streamlit Cloud Diagnostic")
st.success("✅ App reached the first line successfully!")

try:
    st.write("**Python version:**", sys.version)
    st.write("**Working directory:**", os.getcwd())
    st.write("**Files in directory:**", os.listdir("."))
    
    # Test imports one by one
    st.subheader("Testing Imports")
    
    import pandas as pd
    st.success("✅ pandas imported")
    
    import plotly
    st.success("✅ plotly imported")
    
    import yfinance as yf
    st.success("✅ yfinance imported")
    
    st.success("**All critical imports successful!**")
    st.balloons()

except Exception as e:
    st.error("Error during startup")
    st.exception(e)

st.info("If you see this page → the platform works. We can now add your code back gradually.")