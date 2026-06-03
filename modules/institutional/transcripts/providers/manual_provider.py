"""
modules/institutional/transcripts/providers/manual_provider.py
"""

from __future__ import annotations

from typing import Optional

from ..transcript_provider import TranscriptProvider, TranscriptProviderResult


class ManualTranscriptProvider(TranscriptProvider):
    provider_name = "manual"
    display_name = "Manual Upload"

    def fetch_latest_transcript(self, symbol: str) -> Optional[TranscriptProviderResult]:
        # Manual provider intentionally does not fetch remotely.
        return None
