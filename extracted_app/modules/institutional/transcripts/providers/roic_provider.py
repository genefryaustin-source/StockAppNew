"""
modules/institutional/transcripts/providers/roic_provider.py

ROIC.ai provider scaffold.

ROIC API details may differ by account/contract. This file is production-safe:
- Disabled automatically when ROIC_API_KEY is not configured.
- Uses conservative endpoint patterns.
- Returns structured failures instead of breaking the UI.

Update `base_url` and payload parsing once your ROIC API documentation is confirmed.
"""

from __future__ import annotations

from typing import Optional

import requests

from ..secret_utils import get_roic_key
from ..transcript_normalizer import clean_transcript_text, parse_event_date
from ..transcript_provider import TranscriptProvider, TranscriptProviderError, TranscriptProviderResult


class ROICProvider(TranscriptProvider):

    def __init__(self, *, base_url="https://api.roic.ai", **kwargs):
        api_key = get_roic_key()

        print("=" * 60)
        print("ROIC PROVIDER INIT")
        print("API KEY FOUND:", bool(api_key))
        print("API KEY PREFIX:", api_key[:10] if api_key else None)
        print("=" * 60)

        super().__init__(
            enabled=bool(api_key),
            **kwargs
        )

        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def fetch_latest_transcript(
            self,
            symbol: str,
    ) -> Optional[TranscriptProviderResult]:

        if not self.api_key:
            return None

        sym = self._normalize_symbol(symbol)

        # Most recent completed quarter
        from datetime import datetime

        now = datetime.utcnow()

        year = now.year

        if now.month <= 3:
            year -= 1
            quarter = 4
        elif now.month <= 6:
            quarter = 1
        elif now.month <= 9:
            quarter = 2
        else:
            quarter = 3

        url = (
            f"https://api.roic.ai/v2/company/"
            f"earnings-calls/transcript/{sym}"
        )

        params = {
            "apikey": self.api_key,
            "year": year,
            "quarter": quarter,
        }

        response = requests.get(
            url,
            params=params,
            timeout=self.timeout_seconds,
        )

        print("ROIC URL:", response.url)
        print("ROIC STATUS:", response.status_code)

        if response.status_code != 200:
            raise TranscriptProviderError(
                f"ROIC transcript API error {response.status_code}",
                provider_name=self.provider_name,
                status_code=response.status_code,
                payload={"body": response.text[:1000]},
            )

        payload = response.json()

        transcript = clean_transcript_text(
            payload.get("content", "")
        )

        if not transcript:
            return None

        return TranscriptProviderResult(
            symbol=sym,
            transcript_text=transcript,
            provider_name=self.provider_name,
            source_url=response.url,
            fiscal_year=payload.get("year"),
            fiscal_quarter=payload.get("quarter"),
            event_date=parse_event_date(payload.get("date")),
            title=f"{sym} Earnings Call Transcript",
            metadata={
                "provider": "ROIC",
            },
        )
