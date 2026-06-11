import streamlit as st

from modules.help.help_home import render_help_home
from modules.help.help_getting_started import render_help_getting_started
from modules.help.help_stock_research import render_help_stock_research
from modules.help.help_portfolio import render_help_portfolio
from modules.help.help_options import render_help_options
from modules.help.help_ipo import render_help_ipo
from modules.help.help_preipo import render_help_preipo
from modules.help.help_ai import render_help_ai
from modules.help.help_crypto import render_help_crypto
from modules.help.help_admin import render_help_admin
from modules.help.help_analytics_fabric import render_help_analytics_fabric
from modules.help.help_api_providers import render_help_api_providers
from modules.help.help_troubleshooting import render_help_troubleshooting


def render_help():

    st.sidebar.markdown("## 📘 Help Center")

    section = st.sidebar.radio(
        "Documentation",
        [
            "Home",
            "Getting Started",
            "Stock Research",
            "Portfolio",
            "Options",
            "IPO Intelligence",
            "Pre-IPO Intelligence",
            "AI Modules",
            "Crypto",
            "Admin",
            "Analytics Fabric",
            "API Providers",
            "Troubleshooting",
        ],
        key="help_section",
    )

    if section == "Home":
        render_help_home()

    elif section == "Getting Started":
        render_help_getting_started()

    elif section == "Stock Research":
        render_help_stock_research()

    elif section == "Portfolio":
        render_help_portfolio()

    elif section == "Options":
        render_help_options()

    elif section == "IPO Intelligence":
        render_help_ipo()

    elif section == "Pre-IPO Intelligence":
        render_help_preipo()

    elif section == "AI Modules":
        render_help_ai()

    elif section == "Crypto":
        render_help_crypto()

    elif section == "Admin":
        render_help_admin()

    elif section == "Analytics Fabric":
        render_help_analytics_fabric()

    elif section == "API Providers":
        render_help_api_providers()

    elif section == "Troubleshooting":
        render_help_troubleshooting()