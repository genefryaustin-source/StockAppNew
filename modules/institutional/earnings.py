import json
import os
import re
from datetime import datetime, UTC
from typing import Optional, List, Dict, Tuple, Any

import requests
from sqlalchemy.orm import Session

from modules.institutional.models import EarningsEvent

try:
    from modules.institutional.transcripts import build_transcript_service
except Exception:
    build_transcript_service = None


BASE_URL = "https://api.massive.com"
TIMEOUT = 15


# ============================================================
# SECRETS
# ============================================================

def _read_streamlit_secret(path: str) -> Optional[str]:
    """
    Read a Streamlit secret using dotted paths.

    Supports examples like:
        OPENAI_API_KEY
        ANTHROPIC_API_KEY
        openai.api_key
        anthropic.api_key
        llm.openai_api_key
        llm.anthropic_api_key
        market_data.MASSIVE_API_KEY
    """
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


def _get_secret_value(
    *,
    env_names: List[str],
    streamlit_paths: List[str],
) -> Optional[str]:
    for path in streamlit_paths:
        value = _read_streamlit_secret(path)
        if value:
            return value

    for name in env_names:
        value = os.getenv(name)
        if value:
            return value.strip()

    return None


def _get_secret_api_key() -> Optional[str]:
    """
    Massive/market-data API key retrieval for local Streamlit, Streamlit Cloud,
    and environment variables.
    """
    return _get_secret_value(
        env_names=[
            "MASSIVE_API_KEY",
            "MARKETDATA_API_KEY",
            "POLYGON_API_KEY",
        ],
        streamlit_paths=[
            "MASSIVE_API_KEY",
            "massive_api_key",
            "MARKETDATA_API_KEY",
            "market_data.MASSIVE_API_KEY",
            "market_data.massive_api_key",
            "market_data.MARKETDATA_API_KEY",
            "POLYGON_API_KEY",
            "market_data.POLYGON_API_KEY",
        ],
    )


def _get_openai_key() -> Optional[str]:
    return _get_secret_value(
        env_names=[
            "OPENAI_API_KEY",
            "OPENAI_KEY",
        ],
        streamlit_paths=[
            "OPENAI_API_KEY",
            "openai_api_key",
            "OPENAI_KEY",
            "openai.OPENAI_API_KEY",
            "openai.api_key",
            "llm.OPENAI_API_KEY",
            "llm.openai_api_key",
        ],
    )


def _get_anthropic_key() -> Optional[str]:
    return _get_secret_value(
        env_names=[
            "ANTHROPIC_API_KEY",
            "ANTHROPIC_KEY",
        ],
        streamlit_paths=[
            "ANTHROPIC_API_KEY",
            "anthropic_api_key",
            "ANTHROPIC_KEY",
            "anthropic.ANTHROPIC_API_KEY",
            "anthropic.api_key",
            "llm.ANTHROPIC_API_KEY",
            "llm.anthropic_api_key",
        ],
    )


# ============================================================
# EARNINGS EVENTS
# ============================================================

def _parse_iso_date(d: str):
    if not d:
        return None

    try:
        if len(d) == 10:
            return datetime.fromisoformat(d).replace(tzinfo=UTC)

        return datetime.fromisoformat(d.replace("Z", "+00:00")).astimezone(UTC)

    except Exception:
        return None


def _to_float_safe(v):
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def ingest_massive_earnings(
    db: Session,
    tenant_id: str,
    symbol: str,
    limit: int = 50,
) -> int:
    """
    Massive endpoint used: /vX/reference/financials.
    Stores any EPS/revenue values into eps_est/rev_est fields.
    """
    api_key = _get_secret_api_key()

    if not api_key:
        raise Exception(
            "Massive API key missing. Set MASSIVE_API_KEY or market_data.MASSIVE_API_KEY in secrets.toml."
        )

    sym = symbol.upper().strip()

    url = f"{BASE_URL}/vX/reference/financials"
    params = {
        "ticker": sym,
        "limit": limit,
        "apiKey": api_key,
    }

    response = requests.get(url, params=params, timeout=TIMEOUT)

    if response.status_code != 200:
        raise Exception(f"Massive Earnings API error {response.status_code}: {response.text}")

    data = response.json()
    results = data.get("results") or []

    if not results:
        return 0

    inserted = 0

    for item in results:
        filing_date = (
            item.get("filing_date")
            or item.get("end_date")
            or item.get("period_end_date")
        )

        event_date = _parse_iso_date(filing_date)

        if not event_date:
            continue

        exists = (
            db.query(EarningsEvent)
            .filter(
                EarningsEvent.tenant_id == tenant_id,
                EarningsEvent.symbol == sym,
                EarningsEvent.event_date == event_date,
            )
            .first()
        )

        if exists:
            continue

        financials = item.get("financials") or {}
        income = financials.get("income_statement") or {}

        def _val(x):
            if x is None:
                return None
            if isinstance(x, dict):
                return x.get("value")
            return x

        eps_value = (
            _val(income.get("basic_earnings_per_share"))
            or _val(income.get("diluted_earnings_per_share"))
        )

        rev_value = (
            _val(income.get("revenues"))
            or _val(income.get("revenue"))
        )

        event = EarningsEvent(
            tenant_id=tenant_id,
            symbol=sym,
            event_date=event_date,
            time_of_day=None,
            eps_est=_to_float_safe(eps_value),
            rev_est=_to_float_safe(rev_value),
        )

        db.add(event)
        inserted += 1

    db.commit()
    return inserted


def list_upcoming(db: Session, tenant_id: str, limit: int = 200):
    return (
        db.query(EarningsEvent)
        .filter(EarningsEvent.tenant_id == tenant_id)
        .order_by(EarningsEvent.event_date.desc())
        .limit(limit)
        .all()
    )


def get_latest_transcript_event(
    db: Session,
    tenant_id: str,
    symbol: str,
) -> Optional[EarningsEvent]:
    sym = symbol.upper().strip()

    if not sym:
        return None

    from sqlalchemy import func

    return (
        db.query(EarningsEvent)
        .filter(
            EarningsEvent.tenant_id == tenant_id,
            EarningsEvent.symbol == sym,
            EarningsEvent.transcript_text != None,
            func.length(EarningsEvent.transcript_text) >= 1000,
        )
        .order_by(EarningsEvent.event_date.desc())
        .first()
    )


# ============================================================
# TRANSCRIPT SERVICE INTEGRATION
# ============================================================

_TRANSCRIPT_SERVICE = None


def get_transcript_service():
    """
    Lazily build the transcript service.

    Requires the Phase 3 subsystem:
        modules/institutional/transcripts/
    """
    global _TRANSCRIPT_SERVICE

    if _TRANSCRIPT_SERVICE is not None:
        return _TRANSCRIPT_SERVICE

    if build_transcript_service is None:
        return None

    _TRANSCRIPT_SERVICE = build_transcript_service()
    return _TRANSCRIPT_SERVICE


def fetch_earnings_transcript(
    db: Session,
    tenant_id: str,
    symbol: str,
    event_date: Optional[datetime] = None,
    source: str = "registry",
    force_refresh: bool = False,
) -> Optional[str]:
    """
    Fetch/cache latest transcript using the provider registry subsystem.

    Flow:
        cache -> ROIC/Quartr/FMP legacy/future providers -> cache result

    Returns:
        transcript text if available, otherwise None.
    """
    sym = symbol.upper().strip()

    if not sym:
        return None

    service = get_transcript_service()

    if service is None:
        # Safe fallback to existing DB cache only.
        event = get_latest_transcript_event(db, tenant_id, sym)
        if event and event.transcript_text:
            return event.transcript_text
        return None

    result = service.get_or_fetch_latest(
        db=db,
        tenant_id=tenant_id,
        symbol=sym,
        force_refresh=force_refresh,
    )

    return result.transcript_text if result and result.success else None


def fetch_earnings_transcript_result(
    db: Session,
    tenant_id: str,
    symbol: str,
    force_refresh: bool = False,
):
    """
    Same as fetch_earnings_transcript, but returns the full service result
    for UI diagnostics: source, cached flag, provider attempts, message, etc.
    """
    sym = symbol.upper().strip()

    service = get_transcript_service()

    if service is None:
        event = get_latest_transcript_event(db, tenant_id, sym)
        if event and event.transcript_text:
            return {
                "success": True,
                "symbol": sym,
                "source": getattr(event, "transcript_source", "cache") or "cache",
                "cached": True,
                "message": f"Loaded cached transcript for {sym}.",
                "transcript_text": event.transcript_text,
                "transcript_chars": len(event.transcript_text or ""),
                "provider_attempts": [],
            }

        return {
            "success": False,
            "symbol": sym,
            "source": "none",
            "cached": False,
            "message": (
                "Transcript subsystem is not installed. "
                "Install modules/institutional/transcripts/ or upload a transcript manually."
            ),
            "transcript_text": None,
            "transcript_chars": 0,
            "provider_attempts": [],
        }

    result = service.get_or_fetch_latest(
        db=db,
        tenant_id=tenant_id,
        symbol=sym,
        force_refresh=force_refresh,
    )

    return result.as_dict()


def provider_status() -> List[Dict[str, Any]]:
    service = get_transcript_service()

    if service is None:
        return [
            {
                "provider_name": "transcript_subsystem",
                "enabled": False,
                "status": "NOT_INSTALLED",
            }
        ]

    return service.provider_status()


# ============================================================
# MANUAL TRANSCRIPT STORAGE / CHUNKING
# ============================================================

def parse_and_chunk_transcript(
    transcript_text: str,
    chunk_size: int = 512,
    overlap: int = 50,
) -> List[Dict[str, str]]:
    """
    Parse transcript into overlapping chunks for future embedding/retrieval.
    """
    if not transcript_text:
        return []

    sentences = re.split(r"(?<=[.!?])\s+", transcript_text)

    chunks = []
    current_chunk = []
    current_length = 0

    for sentence in sentences:
        sentence_words = len(sentence.split())
        current_length += sentence_words
        current_chunk.append(sentence)

        if current_length >= chunk_size:
            chunk_text = " ".join(current_chunk)
            chunks.append(
                {
                    "text": chunk_text,
                    "timestamp": None,
                }
            )

            overlap_words = 0
            overlap_buffer = []

            for sent in reversed(current_chunk):
                overlap_words += len(sent.split())
                overlap_buffer.insert(0, sent)

                if overlap_words >= overlap:
                    break

            current_chunk = overlap_buffer
            current_length = overlap_words

    if current_chunk:
        chunks.append(
            {
                "text": " ".join(current_chunk),
                "timestamp": None,
            }
        )

    return chunks


def store_transcript_and_chunks(
    db: Session,
    tenant_id: str,
    symbol: str,
    event_date: datetime,
    transcript_text: str,
    transcript_url: Optional[str] = None,
    source: str = "manual",
) -> Tuple[bool, str]:
    """
    Store transcript in EarningsEvent and prepare chunks for vector DB.
    Uses TranscriptService cache path when available, otherwise direct ORM fallback.
    """
    sym = symbol.upper().strip()

    try:
        service = get_transcript_service()

        if service is not None:
            result = service.store_manual_transcript(
                db=db,
                tenant_id=tenant_id,
                symbol=sym,
                transcript_text=transcript_text,
                event_date=event_date,
                transcript_url=transcript_url,
                source=source,
            )
            return result.success, result.message

        event = (
            db.query(EarningsEvent)
            .filter(
                EarningsEvent.tenant_id == tenant_id,
                EarningsEvent.symbol == sym,
                EarningsEvent.event_date == event_date,
            )
            .first()
        )

        if not event:
            event = EarningsEvent(
                tenant_id=tenant_id,
                symbol=sym,
                event_date=event_date,
                transcript_text=transcript_text,
                transcript_url=transcript_url,
                transcript_fetched_at=datetime.now(UTC),
                transcript_source=source,
                transcript_chunks_indexed=False,
            )
            db.add(event)
        else:
            event.transcript_text = transcript_text
            event.transcript_url = transcript_url
            event.transcript_fetched_at = datetime.now(UTC)
            event.transcript_source = source
            event.transcript_chunks_indexed = False

        db.commit()

        chunks = parse_and_chunk_transcript(transcript_text)
        return True, f"Transcript stored with {len(chunks)} chunks ready for embedding."

    except Exception as e:
        db.rollback()
        return False, f"Error storing transcript: {str(e)}"


# ============================================================
# AI Q&A
# ============================================================

def _normalize_llm_provider(provider: str) -> str:
    value = str(provider or "").strip().lower()

    if "anthropic" in value or "claude" in value:
        return "anthropic"

    if "openai" in value or "gpt" in value:
        return "openai"

    return value


def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None

    json_match = re.search(r"\{.*\}", text, re.DOTALL)

    if not json_match:
        return None

    try:
        return json.loads(json_match.group())
    except Exception:
        return None


def _truncate_transcript_for_llm(transcript_text: str, max_chars: int = 70000) -> str:
    """
    Prevent runaway context usage while preserving beginning and end of transcript.
    """
    text = transcript_text or ""

    if len(text) <= max_chars:
        return text

    half = max_chars // 2

    return (
        text[:half]
        + "\n\n[... transcript truncated for model context ...]\n\n"
        + text[-half:]
    )


def query_transcript_with_llm(
    transcript_text: str,
    query: str,
    llm_provider: str = "openai",
) -> Optional[Dict[str, Any]]:
    """
    Use LLM to answer a question about an earnings transcript.
    """
    if not transcript_text:
        return {
            "answer": "No transcript text was provided.",
            "citations": [],
            "error": "missing_transcript",
        }

    if len(transcript_text.strip()) < 1000:
        return {
            "answer": (
                "The stored text is too short to be a full earnings call transcript. "
                "Load or upload the complete transcript first."
            ),
            "citations": [],
            "error": "transcript_too_short",
        }

    provider = _normalize_llm_provider(llm_provider)

    try:
        if provider == "openai":
            return _query_openai(transcript_text, query)

        if provider == "anthropic":
            return _query_anthropic(transcript_text, query)

        return {
            "answer": f"Unsupported LLM provider: {llm_provider}",
            "citations": [],
            "error": "unsupported_provider",
        }

    except Exception as e:
        return {
            "answer": "Failed to generate answer. Check API key settings.",
            "citations": [],
            "error": str(e),
        }


def _query_openai(transcript_text: str, query: str) -> Optional[Dict[str, Any]]:
    api_key = _get_openai_key()

    if not api_key:
        return {
            "answer": (
                "OpenAI API key missing. Set OPENAI_API_KEY in "
                ".streamlit/secrets.toml or Streamlit Cloud secrets."
            ),
            "citations": [],
            "error": "missing_openai_api_key",
        }

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)

        system_prompt = """You are a financial analyst reviewing earnings call transcripts.
Answer only from the provided transcript.
If the transcript does not contain enough information, say that clearly.
Return valid JSON only in this format:
{"answer": "...", "citations": ["short exact quote 1", "short exact quote 2"]}
"""

        user_message = f"""Transcript:
{_truncate_transcript_for_llm(transcript_text)}

Question:
{query}

Respond with valid JSON only."""

        response = client.chat.completions.create(
            model=os.getenv("OPENAI_TRANSCRIPT_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
        )

        result_text = response.choices[0].message.content or ""
        result = _extract_json_object(result_text)

        if result:
            result.setdefault("citations", [])
            return result

        return {
            "answer": result_text,
            "citations": [],
        }

    except Exception as e:
        return {
            "answer": (
                "Failed to generate answer with OpenAI. "
                "Check API key settings, model access, and package installation."
            ),
            "citations": [],
            "error": str(e),
        }


def _query_anthropic(transcript_text: str, query: str) -> Optional[Dict[str, Any]]:
    api_key = _get_anthropic_key()

    if not api_key:
        return {
            "answer": (
                "Anthropic API key missing. Set ANTHROPIC_API_KEY in "
                ".streamlit/secrets.toml or Streamlit Cloud secrets."
            ),
            "citations": [],
            "error": "missing_anthropic_api_key",
        }

    try:
        from anthropic import Anthropic

        client = Anthropic(api_key=api_key)

        system_prompt = """You are a financial analyst reviewing earnings call transcripts.
Answer only from the provided transcript.
If the transcript does not contain enough information, say that clearly.
Return valid JSON only in this format:
{"answer": "...", "citations": ["short exact quote 1", "short exact quote 2"]}
"""

        user_message = f"""Transcript:
{_truncate_transcript_for_llm(transcript_text)}

Question:
{query}

Respond with valid JSON only."""

        response = client.messages.create(
            model=os.getenv("ANTHROPIC_TRANSCRIPT_MODEL", "claude-sonnet-4-20250514"),
            max_tokens=1500,
            temperature=0.2,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": user_message,
                }
            ],
        )

        result_text = ""

        for block in response.content:
            if getattr(block, "type", None) == "text":
                result_text += block.text

        result = _extract_json_object(result_text)

        if result:
            result.setdefault("citations", [])
            return result

        return {
            "answer": result_text,
            "citations": [],
        }

    except Exception as e:
        return {
            "answer": (
                "Failed to generate answer with Anthropic. "
                "Check API key settings, model access, and package installation."
            ),
            "citations": [],
            "error": str(e),
        }


# ============================================================
# COMPARISON
# ============================================================

def generate_comparison_table(
    db: Session,
    tenant_id: str,
    symbols: List[str],
    metric: str,
    query: str = None,
    llm_provider: str = "openai",
) -> Optional[Dict[str, Any]]:
    try:
        import pandas as pd

        comparison_data = []
        citations_map = {}

        for symbol in symbols:
            sym = symbol.upper().strip()

            if not sym:
                continue

            transcript = fetch_earnings_transcript(
                db=db,
                tenant_id=tenant_id,
                symbol=sym,
                force_refresh=False,
            )

            if not transcript:
                continue

            question = query or f"What was the {metric} mentioned in this earnings call?"

            result = query_transcript_with_llm(
                transcript,
                question,
                llm_provider=llm_provider,
            )

            if result and not result.get("error"):
                event = get_latest_transcript_event(db, tenant_id, sym)

                comparison_data.append(
                    {
                        "Symbol": sym,
                        "Value": result.get("answer", "N/A"),
                        "Date": (
                            event.event_date.strftime("%Y-%m-%d")
                            if event and event.event_date
                            else "N/A"
                        ),
                    }
                )

                citations_map[sym] = result.get("citations", [])

        if not comparison_data:
            return None

        df = pd.DataFrame(comparison_data)

        return {
            "table": df,
            "citations": citations_map,
        }

    except Exception as e:
        print(f"Comparison table error: {e}")
        return None
