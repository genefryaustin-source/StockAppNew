from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import streamlit as st


@dataclass(frozen=True)
class PortalVersion:
    portal_version: str
    build_date: str
    git_commit: str
    git_branch: str
    environment: str
    document_count: int


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _run_git(*args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=_project_root(),
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return completed.stdout.strip()
    except Exception:
        return "unknown"


def get_portal_version(document_count: int) -> PortalVersion:
    manifest_path = Path(__file__).resolve().parents[2] / "manifest" / "portal-version.json"

    manifest: dict[str, Any] = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            manifest = {}

    return PortalVersion(
        portal_version=str(manifest.get("portal_version", "1.5.0")),
        build_date=str(
            manifest.get(
                "build_date",
                datetime.now(timezone.utc).isoformat(),
            )
        ),
        git_commit=os.getenv("GIT_COMMIT") or _run_git("rev-parse", "--short", "HEAD"),
        git_branch=os.getenv("GIT_BRANCH") or _run_git("branch", "--show-current"),
        environment=os.getenv("APP_ENV", os.getenv("ENVIRONMENT", "development")),
        document_count=document_count,
    )


def render_version_panel(version: PortalVersion) -> None:
    with st.expander("Portal Build Information", expanded=False):
        st.code(
            "\n".join(
                [
                    f"Portal version: {version.portal_version}",
                    f"Build date: {version.build_date}",
                    f"Git commit: {version.git_commit}",
                    f"Git branch: {version.git_branch}",
                    f"Environment: {version.environment}",
                    f"Registered documents: {version.document_count}",
                ]
            ),
            language="text",
        )
