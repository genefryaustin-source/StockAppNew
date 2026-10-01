"""
modules/legal_portal/legal_backup.py

Builds the downloadable backup/evidence archive for the Legal Portal's
"Legal Backup & Recovery" dashboard (super-admin only, see
legal_recovery_dashboard.py). Wraps the existing evidence-export machinery
(legal_evidence.build_evidence_package) together with a checksum manifest,
packaged as an in-memory zip file.

This file was referenced by __init__.py and legal_recovery_dashboard.py
but never actually existed on disk -- the Legal Portal dashboard button
was wired up before this piece was written, which is why importing
modules.legal_portal raised ModuleNotFoundError.
"""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from datetime import datetime, timezone

from .legal_evidence import build_evidence_package, evidence_package_json
from .legal_workflow_service import LegalWorkflowService


def build_legal_backup_archive(
    *,
    service: LegalWorkflowService,
    generated_by: str,
) -> bytes:
    """
    Builds a full legal-compliance backup archive as in-memory zip bytes,
    suitable for st.download_button. Contains:

      - evidence.json: the complete, unfiltered evidence export (every
        document, version, review, and acknowledgement across every
        tenant and user) via legal_evidence.build_evidence_package.
      - manifest.json: generation metadata plus a sha256 checksum of
        evidence.json, so the archive's integrity can be verified later
        independently of the zip container itself.

    Deliberately unfiltered (no user_id/tenant_id/document_key) -- this is
    the "full evidence export" the recovery dashboard's own help text
    promises, not a scoped one.
    """
    package = build_evidence_package(
        service=service,
        generated_by=generated_by,
    )
    evidence_bytes = evidence_package_json(package).encode("utf-8")
    evidence_sha256 = hashlib.sha256(evidence_bytes).hexdigest()

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": generated_by,
        "files": {
            "evidence.json": {
                "sha256": evidence_sha256,
                "bytes": len(evidence_bytes),
            },
        },
    }
    manifest_bytes = json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("evidence.json", evidence_bytes)
        zf.writestr("manifest.json", manifest_bytes)

    return buffer.getvalue()
