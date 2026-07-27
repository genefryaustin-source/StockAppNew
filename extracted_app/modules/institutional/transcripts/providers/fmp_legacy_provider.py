"""
modules/institutional/transcripts/providers/fmp_legacy_provider.py

Kept as a legacy provider only. FMP has restricted this endpoint for newer
accounts, so failures are expected unless the account has legacy access.
"""

from __future__ import annotations

from typing import Optional

import requests

from ..secret_utils import get_fmp_key
from ..transcript_normalizer import clean_transcript_text, parse_event_date
from ..transcript_provider import TranscriptProvider, TranscriptProviderError, TranscriptProviderResult


class FMPLegacyProvider(TranscriptProvider):
    provider_name = "fmp_legacy"
    display_name = "Financial Modeling Prep Legacy"

    def __init__(self, **kwargs):
        api_key = get_fmp_key()
        super().__init__(enabled=bool(api_key), **kwargs)
        self.api_key = api_key

    def fetch_latest_transcript(self, symbol: str) -> Optional[TranscriptProviderResult]:
        if not self.api_key:
            return None

        sym = self._normalize_symbol(symbol)
        url = f"https://financialmodelingprep.com/api/v3/earning_call_transcript/{sym}?apikey={self.api_key}"

        response = requests.get(url, timeout=self.timeout_seconds)

        if response.status_code == 403:
            raise TranscriptProviderError(
                "FMP legacy transcript endpoint is not available for this account.",
                provider_name=self.provider_name,
                status_code=response.status_code,
                payload={"body": response.text[:500]},
            )

        if response.status_code != 200:
            raise TranscriptProviderError(
                f"FMP transcript API error {response.status_code}",
                provider_name=self.provider_name,
                status_code=response.status_code,
                payload={"body": response.text[:500]},
            )

        data = response.json()
        if not data:
            return None

        latest = data[0]
        transcript = clean_transcript_text(
            latest.get("content")
            or latest.get("transcript")
            or latest.get("text")
            or ""
        )

        if not transcript:
            return None

        return TranscriptProviderResult(
            symbol=sym,
            transcript_text=transcript,
            provider_name=self.provider_name,
            source_url=url,
            fiscal_year=latest.get("year"),
            fiscal_quarter=latest.get("quarter"),
            event_date=parse_event_date(latest.get("date")),
            title=f"{sym} Earnings Call Transcript",
            metadata={"raw_keys": list(latest.keys())},
        )
