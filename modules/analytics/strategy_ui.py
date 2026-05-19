from __future__ import annotations

import streamlit as st

from modules.analytics.strategy_discovery import render_strategy_discovery


def render_strategy_ui(db, user):

    st.header("Strategy Discovery")

    render_strategy_discovery(db, user)