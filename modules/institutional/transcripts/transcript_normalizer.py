"""
modules/institutional/transcripts/transcript_normalizer.py

Normalization helpers for transcript text and provider payloads.
"""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean_transcript_text(text: str) -> str:
    if not text:
        return ""

    value = str(text)
    value = html.unescape(value)
    value = re.sub(r"<script[\s\S]*?</script>", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"<style[\s\S]*?</style>", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"<[^>]+>", " ", value)
    value = value.replace("\xa0", " ")
    value = re.sub(r"\r\n|\r", "\n", value)
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    value = "\n".join(line.strip() for line in value.splitlines())
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def parse_event_date(value: Any) -> Optional[str]:
    if not value:
        return None

    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()

    text = str(value).strip()
    if not text:
        return None

    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(text[:10], fmt).replace(tzinfo=timezone.utc).isoformat()
        except Exception:
            pass

    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()
    except Exception:
        return None


def extract_first_text(payload: Dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return clean_transcript_text(value)
    return ""


def transcript_preview(text: str, length: int = 500) -> str:
    value = clean_transcript_text(text)
    return value[:length] + ("..." if len(value) > length else "")
