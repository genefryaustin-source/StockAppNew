from __future__ import annotations

import re
from functools import lru_cache
from html import unescape
from pathlib import Path

from .legal_registry import LegalDocument


BODY_PATTERN = re.compile(r"<body[^>]*>(.*?)</body>", re.IGNORECASE | re.DOTALL)
SCRIPT_PATTERN = re.compile(r"<script[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL)
STYLE_PATTERN = re.compile(r"<style[^>]*>.*?</style>", re.IGNORECASE | re.DOTALL)
TAG_PATTERN = re.compile(r"<[^>]+>")
SPACE_PATTERN = re.compile(r"\s+")


class LegalDocumentLoadError(RuntimeError):
    pass


@lru_cache(maxsize=64)
def load_document_html(path_text: str) -> str:
    path = Path(path_text)

    if not path.exists():
        raise LegalDocumentLoadError(f"Legal document not found: {path}")

    try:
        html = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        html = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise LegalDocumentLoadError(f"Unable to read legal document: {path}") from exc

    match = BODY_PATTERN.search(html)
    return match.group(1).strip() if match else html.strip()


def load_document(document: LegalDocument) -> str:
    return load_document_html(str(document.source_path))


@lru_cache(maxsize=64)
def load_search_text(path_text: str) -> str:
    html = load_document_html(path_text)
    text = SCRIPT_PATTERN.sub(" ", html)
    text = STYLE_PATTERN.sub(" ", text)
    text = TAG_PATTERN.sub(" ", text)
    text = unescape(text)
    return SPACE_PATTERN.sub(" ", text).strip()


def search_text(document: LegalDocument) -> str:
    return load_search_text(str(document.source_path))


def plain_text(document: LegalDocument) -> str:
    return search_text(document)
