from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable, Optional

from .legal_document_loader import search_text
from .legal_registry import LegalDocument, iter_documents


TOKEN_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")
SPACE_PATTERN = re.compile(r"\s+")


@dataclass(frozen=True)
class SearchResult:
    document: LegalDocument
    score: float
    snippet: str
    matched_terms: tuple[str, ...]
    exact_phrase: bool


def normalize_query(query: str) -> str:
    return SPACE_PATTERN.sub(" ", (query or "").strip())


def tokenize(value: str) -> list[str]:
    return [match.group(0).lower() for match in TOKEN_PATTERN.finditer(value or "")]


@lru_cache(maxsize=64)
def _document_index(document_key: str) -> dict[str, object]:
    document = next(doc for doc in iter_documents() if doc.key == document_key)
    body = search_text(document)

    return {
        "body": body,
        "title_tokens": tokenize(document.title),
        "summary_tokens": tokenize(document.summary),
        "category_tokens": tokenize(document.category),
        "body_tokens": tokenize(body),
        "searchable": " ".join(
            [document.title, document.summary, document.category, body]
        ).lower(),
    }


def _term_frequency(tokens: Iterable[str]) -> dict[str, int]:
    frequency: dict[str, int] = {}
    for token in tokens:
        frequency[token] = frequency.get(token, 0) + 1
    return frequency


def _weighted_score(
    document: LegalDocument,
    terms: list[str],
    phrase: str,
) -> tuple[float, tuple[str, ...], bool]:
    index = _document_index(document.key)

    title_frequency = _term_frequency(index["title_tokens"])
    summary_frequency = _term_frequency(index["summary_tokens"])
    category_frequency = _term_frequency(index["category_tokens"])
    body_frequency = _term_frequency(index["body_tokens"])

    matched: list[str] = []
    score = 0.0

    for term in terms:
        count = (
            title_frequency.get(term, 0)
            + summary_frequency.get(term, 0)
            + category_frequency.get(term, 0)
            + body_frequency.get(term, 0)
        )
        if count == 0:
            continue

        matched.append(term)
        score += title_frequency.get(term, 0) * 12.0
        score += summary_frequency.get(term, 0) * 6.0
        score += category_frequency.get(term, 0) * 5.0
        score += min(body_frequency.get(term, 0), 12) * 1.2

    exact_phrase = bool(phrase and phrase.lower() in index["searchable"])
    if exact_phrase:
        score += 18.0

    if document.title.lower() == phrase.lower():
        score += 40.0
    elif phrase.lower() in document.title.lower():
        score += 24.0

    coverage = len(matched) / max(1, len(terms))
    score *= 0.55 + (coverage * 0.45)

    return score, tuple(sorted(set(matched))), exact_phrase


def _snippet(text: str, terms: list[str], phrase: str, radius: int = 170) -> str:
    lowered = text.lower()
    position = lowered.find(phrase.lower()) if phrase else -1

    if position < 0:
        positions = [lowered.find(term) for term in terms if lowered.find(term) >= 0]
        position = min(positions) if positions else 0

    start = max(0, position - radius)
    end = min(len(text), position + max(len(phrase), 1) + radius)

    snippet = text[start:end].strip()
    if start:
        snippet = "..." + snippet
    if end < len(text):
        snippet += "..."

    return snippet


def search_documents(
    query: str,
    *,
    category: Optional[str] = None,
    limit: int = 25,
    require_all_terms: bool = False,
) -> list[SearchResult]:
    normalized = normalize_query(query)
    if len(normalized) < 2:
        return []

    terms = tokenize(normalized)
    if not terms:
        return []

    results: list[SearchResult] = []

    for document in iter_documents(category):
        score, matched_terms, exact_phrase = _weighted_score(
            document,
            terms,
            normalized,
        )

        if not matched_terms:
            continue

        if require_all_terms and len(matched_terms) < len(set(terms)):
            continue

        body = _document_index(document.key)["body"]

        results.append(
            SearchResult(
                document=document,
                score=round(score, 3),
                snippet=_snippet(body, terms, normalized),
                matched_terms=matched_terms,
                exact_phrase=exact_phrase,
            )
        )

    results.sort(
        key=lambda item: (
            -item.score,
            item.document.category,
            item.document.title,
        )
    )

    return results[:limit]


def suggested_queries() -> tuple[str, ...]:
    return (
        "investment advice",
        "artificial intelligence",
        "market data",
        "cookies",
        "security",
        "risk of loss",
        "API access",
        "privacy rights",
    )
