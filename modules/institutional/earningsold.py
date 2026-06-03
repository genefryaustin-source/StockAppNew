import requests
from datetime import datetime, UTC
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Tuple
import re

from modules.institutional.models import EarningsEvent

BASE_URL = "https://api.massive.com"
TIMEOUT = 15


def _get_secret_api_key() -> str | None:
    """
    Robust API key retrieval for Streamlit (local + Cloud).
    Checks multiple common patterns used by developers.
    """
    try:
        import streamlit as st

        # Possible key names (in order of preference)
        key_names = ["MASSIVE_API_KEY", "massive_api_key", "MARKETDATA_API_KEY"]

        # 1. Top-level secrets (most common on Streamlit Cloud)
        for name in key_names:
            key = st.secrets.get(name)
            if key:
                return key

        # 2. Nested under 'market_data' section
        if "market_data" in st.secrets:
            for name in key_names:
                key = st.secrets["market_data"].get(name)
                if key:
                    return key

        # 3. Legacy fallback patterns
        legacy_patterns = [
            st.secrets.get("POLYGON_API_KEY"),
            st.secrets["market_data"].get("POLYGON_API_KEY") if "market_data" in st.secrets else None,
        ]
        for key in legacy_patterns:
            if key:
                return key

        return None

    except Exception:
        # Graceful fallback when streamlit is not available (e.g. tests)
        return None


def _parse_iso_date(d: str):
    if not d:
        return None
    try:
        # handle YYYY-MM-DD
        if len(d) == 10:
            return datetime.fromisoformat(d).replace(tzinfo=UTC)
        # handle full iso datetime
        return datetime.fromisoformat(d.replace("Z", "+00:00")).astimezone(UTC)
    except Exception:
        return None


def ingest_massive_earnings(db: Session, tenant_id: str, symbol: str, limit: int = 50) -> int:
    """
    Massive endpoint used: /vX/reference/financials
    This is financial filings history; Massive may not provide estimates.
    We store any EPS/revenue values we can find into eps_est/rev_est fields.
    """
    api_key = _get_secret_api_key()
    if not api_key:
        raise Exception("Massive API key missing (set market_data.MASSIVE_API_KEY in secrets.toml)")

    sym = symbol.upper()

    url = f"{BASE_URL}/vX/reference/financials"
    params = {
        "ticker": sym,
        "limit": limit,
        "apiKey": api_key,
    }

    r = requests.get(url, params=params, timeout=TIMEOUT)
    if r.status_code != 200:
        raise Exception(f"Massive Earnings API error {r.status_code}: {r.text}")

    data = r.json()
    results = data.get("results") or []
    if not results:
        return 0

    inserted = 0

    for item in results:
        filing_date = item.get("filing_date") or item.get("end_date") or item.get("period_end_date")
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

        # Robust parsing: Massive objects often look like {"value": ...}
        def _val(x):
            if x is None:
                return None
            if isinstance(x, dict):
                return x.get("value")
            return x

        eps_value = _val(income.get("basic_earnings_per_share")) or _val(income.get("diluted_earnings_per_share"))
        rev_value = _val(income.get("revenues")) or _val(income.get("revenue"))

        # IMPORTANT: do NOT use eps_actual/revenue_actual fields in ORM kwargs
        ev = EarningsEvent(
            tenant_id=tenant_id,
            symbol=sym,
            event_date=event_date,
            time_of_day=None,
            eps_est=_to_float_safe(eps_value),
            rev_est=_to_float_safe(rev_value),

        )

        db.add(ev)
        inserted += 1

    db.commit()
    return inserted


def _to_float_safe(v):
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def list_upcoming(db: Session, tenant_id: str, limit: int = 200):
    return (
        db.query(EarningsEvent)
        .filter(EarningsEvent.tenant_id == tenant_id)
        .order_by(EarningsEvent.event_date.desc())
        .limit(limit)
        .all()
    )


# ============================================================
# TRANSCRIPT FUNCTIONS (NEW)
# ============================================================

def _get_openai_key() -> str | None:
    """Get OpenAI API key with robust fallback support."""
    try:
        import streamlit as st

        # Try multiple common naming conventions
        for name in ["OPENAI_API_KEY", "openai_api_key", "OPENAI_KEY"]:
            key = st.secrets.get(name)
            if key:
                return key

        # Check under a section if using nested secrets
        if "openai" in st.secrets:
            return st.secrets["openai"].get("OPENAI_API_KEY") or st.secrets["openai"].get("api_key")

        return None
    except Exception:
        return None


def fetch_earnings_transcript(
        db: Session,
        tenant_id: str,
        symbol: str,
        event_date: datetime,
        source: str = "seeking_alpha"
) -> Optional[str]:
    """
    Fetch earnings call transcript from external source.
    Supports multiple sources: seeking_alpha, investor_relations, etc.

    Returns: transcript text if found, None otherwise
    """
    sym = symbol.upper()

    if source == "seeking_alpha":
        return _fetch_seeking_alpha_transcript(sym, event_date)
    elif source == "investor_relations":
        # Placeholder for investor relations website scraping
        return _fetch_investor_relations_transcript(sym, event_date)
    else:
        return None


def _fetch_seeking_alpha_transcript(symbol: str, event_date: datetime) -> Optional[str]:
    """
    Placeholder: In production, integrate with Seeking Alpha API or web scraper.
    For now, returns None to indicate transcript source would be queried here.
    """
    # TODO: Implement actual Seeking Alpha API/scraper integration
    # Example: https://www.seekingalpha.com/api/v3/transcripts?filter[slug]={symbol}
    return None


def _fetch_investor_relations_transcript(symbol: str, event_date: datetime) -> Optional[str]:
    """
    Placeholder: In production, scrape company investor relations sites.
    """
    # TODO: Implement investor relations site scraping
    return None


def parse_and_chunk_transcript(
        transcript_text: str,
        chunk_size: int = 512,
        overlap: int = 50
) -> List[Dict[str, str]]:
    """
    Parse transcript into overlapping chunks for embedding and retrieval.

    Args:
        transcript_text: Raw transcript
        chunk_size: Target tokens per chunk (approximate)
        overlap: Token overlap between chunks

    Returns:
        List of {"text": chunk_text, "timestamp": timestamp_if_available}
    """
    if not transcript_text:
        return []

    # Simple sentence-based chunking (more sophisticated: use token counter)
    sentences = re.split(r'(?<=[.!?])\s+', transcript_text)

    chunks = []
    current_chunk = []
    current_length = 0
    overlap_buffer = []

    for sentence in sentences:
        sentence_words = len(sentence.split())
        current_length += sentence_words
        current_chunk.append(sentence)

        if current_length >= chunk_size:
            chunk_text = ' '.join(current_chunk)
            chunks.append({
                "text": chunk_text,
                "timestamp": None,  # Could extract timestamps if in format like "[00:15:30]"
            })

            # Create overlap by keeping last N sentences
            overlap_words = 0
            overlap_buffer = []
            for sent in reversed(current_chunk):
                overlap_words += len(sent.split())
                overlap_buffer.insert(0, sent)
                if overlap_words >= overlap:
                    break

            current_chunk = overlap_buffer
            current_length = overlap_words

    # Add remaining text
    if current_chunk:
        chunks.append({
            "text": ' '.join(current_chunk),
            "timestamp": None,
        })

    return chunks


def store_transcript_and_chunks(
        db: Session,
        tenant_id: str,
        symbol: str,
        event_date: datetime,
        transcript_text: str,
        transcript_url: Optional[str] = None,
        source: str = "seeking_alpha"
) -> Tuple[bool, str]:
    """
    Store transcript in EarningsEvent and prepare chunks for vector DB.

    Returns: (success: bool, message: str)
    """
    try:
        # Find or create EarningsEvent
        event = (
            db.query(EarningsEvent)
            .filter(
                EarningsEvent.tenant_id == tenant_id,
                EarningsEvent.symbol == symbol.upper(),
                EarningsEvent.event_date == event_date,
            )
            .first()
        )

        if not event:
            event = EarningsEvent(
                tenant_id=tenant_id,
                symbol=symbol.upper(),
                event_date=event_date,
                transcript_text=transcript_text,
                transcript_url=transcript_url,
                transcript_fetched_at=datetime.now(UTC),
                transcript_source=source,
                transcript_chunks_indexed=False,  # Will be set to True after vector DB ingestion
            )
            db.add(event)
        else:
            event.transcript_text = transcript_text
            event.transcript_url = transcript_url
            event.transcript_fetched_at = datetime.now(UTC)
            event.transcript_source = source
            event.transcript_chunks_indexed = False

        db.commit()

        # Parse into chunks (actual vector DB storage happens in UI layer)
        chunks = parse_and_chunk_transcript(transcript_text)

        return True, f"Transcript stored with {len(chunks)} chunks ready for embedding"

    except Exception as e:
        db.rollback()
        return False, f"Error storing transcript: {str(e)}"


def query_transcript_with_llm(
        transcript_text: str,
        query: str,
        llm_provider: str = "openai"
) -> Optional[Dict]:
    """
    Use LLM to answer question about earnings transcript.
    Returns dict with {"answer": str, "citations": List[str]}

    Args:
        transcript_text: Full transcript or relevant chunks
        query: User's natural language question
        llm_provider: "openai", "anthropic", "ollama", etc.
    """
    if not transcript_text:
        return None

    try:
        if llm_provider == "openai":
            return _query_openai(transcript_text, query)
        elif llm_provider == "anthropic":
            return _query_anthropic(transcript_text, query)
        else:
            return None
    except Exception as e:
        print(f"LLM query error: {e}")
        return None


def _query_openai(transcript_text: str, query: str) -> Optional[Dict]:
    """
    Query transcript using OpenAI API.
    """
    api_key = _get_openai_key()
    if not api_key:
        return None

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        system_prompt = """You are a financial analyst reviewing earnings call transcripts.
        When answering questions:
        1. Provide accurate, cited responses
        2. Extract relevant quotes from the transcript
        3. Return answer and citations as JSON: {"answer": "...", "citations": ["quote 1", "quote 2"]}
        """

        user_message = f"""Transcript:
{transcript_text}

Question: {query}

Respond in JSON format."""

        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.3,
        )

        import json
        result_text = response.choices[0].message.content

        # Parse JSON response
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            return result

        return {"answer": result_text, "citations": []}

    except Exception as e:
        print(f"OpenAI error: {e}")
        return None


def _query_anthropic(transcript_text: str, query: str) -> Optional[Dict]:
    """
    Query transcript using Anthropic Claude API.
    """
    st.secrets.get("ANTHROPIC_API_KEY"),
    if not api_key:
        return None
    try:
        from anthropic import Anthropic
        client = Anthropic()

        system_prompt = """You are a financial analyst reviewing earnings call transcripts.
        When answering questions, provide citations from the transcript.
        Return responses in this JSON format: {"answer": "...", "citations": ["quote 1", "quote 2"]}
        """

        user_message = f"""Transcript:
{transcript_text}

Question: {query}"""

        response = client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )

        import json
        result_text = response.content[0].text

        # Parse JSON response
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            return result

        return {"answer": result_text, "citations": []}

    except Exception as e:
        print(f"Anthropic error: {e}")
        return None


def generate_comparison_table(
        db: Session,
        tenant_id: str,
        symbols: List[str],
        metric: str,  # e.g., "revenue_growth", "margin_expansion"
        query: str = None
) -> Optional[Dict]:
    """
    Generate comparison table across multiple companies' transcripts.

    Args:
        symbols: List of stock tickers
        metric: Financial metric to compare
        query: Optional custom query to ask across all transcripts

    Returns:
        {"table": DataFrame, "citations": {symbol: [quotes]}}
    """
    try:
        import pandas as pd

        comparison_data = []
        citations_map = {}

        for symbol in symbols:
            # Get latest earnings event with transcript
            event = (
                db.query(EarningsEvent)
                .filter(
                    EarningsEvent.tenant_id == tenant_id,
                    EarningsEvent.symbol == symbol.upper(),
                    EarningsEvent.transcript_text != None,
                )
                .order_by(EarningsEvent.event_date.desc())
                .first()
            )

            if not event or not event.transcript_text:
                continue

            # Query transcript for the metric
            question = query or f"What was the {metric} mentioned in this earnings call?"
            result = query_transcript_with_llm(event.transcript_text, question)

            if result:
                comparison_data.append({
                    "Symbol": symbol.upper(),
                    "Value": result.get("answer", "N/A"),
                    "Date": event.event_date.strftime("%Y-%m-%d"),
                })
                citations_map[symbol.upper()] = result.get("citations", [])

        if not comparison_data:
            return None

        df = pd.DataFrame(comparison_data)
        return {"table": df, "citations": citations_map}

    except Exception as e:
        print(f"Comparison table error: {e}")
        return None
