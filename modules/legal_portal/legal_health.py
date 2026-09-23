from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import streamlit as st

from .legal_registry import iter_documents


@dataclass(frozen=True)
class LegalHealth:
    status: str
    total_documents: int
    available_documents: int
    missing_documents: tuple[str, ...]


def check_legal_health() -> LegalHealth:
    documents = list(iter_documents())
    missing = tuple(
        document.filename
        for document in documents
        if not document.source_path.exists()
    )

    available = len(documents) - len(missing)
    status = "healthy" if not missing else "degraded"

    return LegalHealth(
        status=status,
        total_documents=len(documents),
        available_documents=available,
        missing_documents=missing,
    )


def render_health_panel(health: LegalHealth) -> None:
    with st.expander("Portal Health", expanded=False):
        if health.status == "healthy":
            st.success(
                f"Legal portal healthy: {health.available_documents}/"
                f"{health.total_documents} registered documents available."
            )
        else:
            st.warning(
                f"Legal portal degraded: {health.available_documents}/"
                f"{health.total_documents} registered documents available."
            )
            st.code("\n".join(health.missing_documents), language="text")
