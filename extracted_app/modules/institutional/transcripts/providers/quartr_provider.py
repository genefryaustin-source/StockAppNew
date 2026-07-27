"""
modules/institutional/transcripts/providers/quartr_provider.py

Quartr provider scaffold.

Quartr is typically a commercial data provider. Endpoint paths may vary by plan.
This provider is safe to keep installed because it disables itself when no
QUARTR_API_KEY is configured.
"""

from __future__ import annotations

from typing import Optional

import requests

from ..secret_utils import get_quartr_key
from ..transcript_normalizer import clean_transcript_text, parse_event_date
from ..transcript_provider import TranscriptProvider, TranscriptProviderError, TranscriptProviderResult


class QuartrProvider(TranscriptProvider):
    provider_name = "quartr"
    display_name = "Quartr"

    def __init__(self, *, base_url: str = "https://api.quartr.com", **kwargs):
        api_key = get_quartr_key()
        super().__init__(enabled=bool(api_key), **kwargs)
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def fetch_latest_transcript(self, symbol: str) -> Optional[TranscriptProviderResult]:
        if not self.api_key:
            return None

        sym = self._normalize_symbol(symbol)
        candidate_urls = [
            f"{self.base_url}/v1/companies/{sym}/events/latest/transcript",
            f"{self.base_url}/v1/transcripts/latest?symbol={sym}",
            f"{self.base_url}/transcripts/latest?symbol={sym}",
        ]

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }

        last_error = None

        for url in candidate_urls:
            try:
                response = requests.get(url, headers=headers, timeout=self.timeout_seconds)

                if response.status_code == 404:
                    continue

                if response.status_code in {401, 403}:
                    raise TranscriptProviderError(
                        "Quartr API key rejected or transcript access denied.",
                        provider_name=self.provider_name,
                        status_code=response.status_code,
                        payload={"url": url, "body": response.text[:500]},
                    )

                if response.status_code != 200:
                    last_error = f"Quartr API error {response.status_code}: {response.text[:300]}"
                    continue

                payload = response.json()
                transcript = clean_transcript_text(
                    payload.get("transcript")
                    or payload.get("content")
                    or payload.get("text")
                    or ""
                )

                if not transcript and isinstance(payload.get("data"), dict):
                    data = payload["data"]
                    transcript = clean_transcript_text(
                        data.get("transcript")
                        or data.get("content")
                        or data.get("text")
                        or ""
                    )
                    payload = data

                if not transcript:
                    continue

                return TranscriptProviderResult(
                    symbol=sym,
                    transcript_text=transcript,
                    provider_name=self.provider_name,
                    source_url=url,
                    fiscal_year=payload.get("year") or payload.get("fiscal_year"),
                    fiscal_quarter=payload.get("quarter") or payload.get("fiscal_quarter"),
                    event_date=parse_event_date(payload.get("date") or payload.get("event_date")),
                    title=payload.get("title") or f"{sym} Earnings Call Transcript",
                    metadata={"provider_payload_keys": list(payload.keys())},
                )

            except TranscriptProviderError:
                raise
            except Exception as exc:
                last_error = str(exc)

        if last_error:
            raise TranscriptProviderError(
                last_error,
                provider_name=self.provider_name,
                payload={"candidate_urls": candidate_urls},
            )

        return None
