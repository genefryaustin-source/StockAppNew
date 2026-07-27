"""
Institutional transcript provider subsystem.

Drop this folder into:
    modules/institutional/transcripts/

Recommended imports:
    from modules.institutional.transcripts.transcript_service import TranscriptService
    from modules.institutional.transcripts.transcript_registry import build_default_transcript_registry
"""

from .transcript_provider import (
    TranscriptProvider,
    TranscriptProviderResult,
    TranscriptProviderStatus,
    TranscriptProviderError,
)
from .transcript_registry import TranscriptRegistry, build_default_transcript_registry
from .transcript_cache import TranscriptCache
from .transcript_service import TranscriptService, build_transcript_service

__all__ = [
    "TranscriptProvider",
    "TranscriptProviderResult",
    "TranscriptProviderStatus",
    "TranscriptProviderError",
    "TranscriptRegistry",
    "build_default_transcript_registry",
    "TranscriptCache",
    "TranscriptService",
    "build_transcript_service",
]
