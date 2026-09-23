from __future__ import annotations
from .legal_components import RelatedDocument
from .legal_registry import DOCUMENTS

RELATIONSHIPS = {
    "privacy-policy": ("cookie-policy","terms-of-service","security"),
    "terms-of-service": ("financial-disclaimer","risk-disclosure","acceptable-use-policy"),
    "cookie-policy": ("privacy-policy","security","terms-of-service"),
    "financial-disclaimer": ("risk-disclosure","ai-disclosure","market-data-disclaimer"),
    "risk-disclosure": ("financial-disclaimer","ai-disclosure","market-data-disclaimer"),
    "ai-disclosure": ("financial-disclaimer","risk-disclosure","terms-of-service"),
    "market-data-disclaimer": ("financial-disclaimer","risk-disclosure","api-license"),
    "acceptable-use-policy": ("terms-of-service","api-license","security"),
    "api-license": ("acceptable-use-policy","security","market-data-disclaimer"),
    "security": ("privacy-policy","acceptable-use-policy","contact"),
    "accessibility": ("contact","privacy-policy"),
    "contact": ("privacy-policy","security","accessibility"),
}

def related_documents(key: str) -> list[RelatedDocument]:
    result = []
    for related_key in RELATIONSHIPS.get(key, ()):
        doc = DOCUMENTS.get(related_key)
        if doc:
            result.append(RelatedDocument(doc.key, doc.title, doc.summary))
    return result
