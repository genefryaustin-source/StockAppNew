import os
import toml
import streamlit as st
from pathlib import Path

def get_app_data_dir():
    base = os.getenv("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    path = os.path.join(base, "EquityResearchTerminal")
    os.makedirs(path, exist_ok=True)
    return path

def load_local_config():
    path = os.path.join(get_app_data_dir(), "config.toml")
    if os.path.exists(path):
        return toml.load(path)
    return {}

LOCAL_CONFIG = load_local_config()

def get_secret(key, default=None):
    try:
        if key in st.secrets:
            return st.secrets.get(key)
    except Exception:
        pass

    if key in LOCAL_CONFIG:
        return LOCAL_CONFIG.get(key)

    val = os.getenv(key)
    if val:
        return val

    return default