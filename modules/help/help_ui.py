import streamlit as st

from modules.help.help_home import render_help_home
from modules.help.help_getting_started import render_help_getting_started

from modules.help.help_stock_research import render_stock_research_help
from modules.help.help_portfolio import render_portfolio_help
from modules.help.help_options import render_options_help
from modules.help.help_ipo import render_ipo_help
from modules.help.help_preipo import render_preipo_help

from modules.help.help_ai import render_ai_help
from modules.help.help_crypto import render_crypto_help
from modules.help.help_admin import render_admin_help

from modules.help.help_analytics_fabric import render_analytics_fabric_help
from modules.help.help_api_providers import render_api_providers_help
from modules.help.help_troubleshooting import render_troubleshooting_help

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
        render_stock_research_help()

    elif section == "Portfolio":
        render_portfolio_help()

    elif section == "Options":
        render_options_help()

    elif section == "IPO Intelligence":
        render_ipo_help()

    elif section == "Pre-IPO Intelligence":
        render_preipo_help()

    elif section == "AI Modules":
        render_ai_help()

    elif section == "Crypto":
        render_crypto_help()

    elif section == "Admin":
        render_admin_help()

    elif section == "Analytics Fabric":
        render_analytics_fabric_help()

    elif section == "API Providers":
        render_api_providers_help()

    elif section == "Troubleshooting":
        render_troubleshooting_help()