"""
modules/institutional/transcripts/secret_utils.py

Shared secrets/env retrieval helpers.
"""

from __future__ import annotations

import os
from typing import Iterable, Optional


def read_streamlit_secret(path: str) -> Optional[str]:
    try:
        import streamlit as st

        current = st.secrets

        for part in path.split("."):
            if hasattr(current, "get"):
                current = current.get(part)
            else:
                current = current[part]

            if current is None:
                return None

        value = str(current).strip()
        return value or None
    except Exception:
        return None


def get_secret_value(
    *,
    env_names: Iterable[str],
    streamlit_paths: Iterable[str],
) -> Optional[str]:
    for path in streamlit_paths:
        value = read_streamlit_secret(path)
        if value:
            return value

    for name in env_names:
        value = os.getenv(name)
        if value:
            return value.strip()

    return None


def get_roic_key() -> Optional[str]:
    return get_secret_value(
        env_names=["ROIC_API_KEY", "ROIC_AI_API_KEY"],
        streamlit_paths=[
            "ROIC_API_KEY",
            "ROIC_AI_API_KEY",
            "roic.api_key",
            "roic_ai.api_key",
            "market_data.ROIC_API_KEY",
        ],
    )


def get_quartr_key() -> Optional[str]:
    return get_secret_value(
        env_names=["QUARTR_API_KEY"],
        streamlit_paths=[
            "QUARTR_API_KEY",
            "quartr.api_key",
            "market_data.QUARTR_API_KEY",
        ],
    )


def get_fmp_key() -> Optional[str]:
    return get_secret_value(
        env_names=["FMP_API_KEY", "FINANCIAL_MODELING_PREP_API_KEY"],
        streamlit_paths=[
            "FMP_API_KEY",
            "FINANCIAL_MODELING_PREP_API_KEY",
            "financial_modeling_prep.api_key",
            "market_data.FMP_API_KEY",
        ],
    )
