from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional


@dataclass(frozen=True)
class LegalDocument:
    key: str
    title: str
    filename: str
    category: str
    summary: str
    version: str = "1.0"
    effective_date: str = "August 1, 2026"
    public_path: Optional[str] = None
    requires_counsel_review: bool = True

    @property
    def source_path(self) -> Path:
        return Path(__file__).resolve().parent / "pages" / self.filename


DOCUMENTS: Dict[str, LegalDocument] = {
    "privacy-policy": LegalDocument(
        key="privacy-policy",
        title="Privacy Policy",
        filename="privacy-policy.html",
        category="Core Legal",
        summary="How AIQ Intellus collects, uses, stores, protects, and discloses information.",
        public_path="/privacy-policy.html",
    ),
    "terms-of-service": LegalDocument(
        key="terms-of-service",
        title="Terms of Service",
        filename="terms-of-service.html",
        category="Core Legal",
        summary="Contractual terms governing access to and use of AIQ Intellus.",
        public_path="/legal/terms-of-service.html",
    ),
    "cookie-policy": LegalDocument(
        key="cookie-policy",
        title="Cookie Policy",
        filename="cookie-policy.html",
        category="Core Legal",
        summary="Cookies, browser storage, authentication sessions, and user controls.",
        public_path="/legal/cookie-policy.html",
    ),
    "financial-disclaimer": LegalDocument(
        key="financial-disclaimer",
        title="Financial Disclaimer",
        filename="financial-disclaimer.html",
        category="Financial Disclosures",
        summary="Important limitations concerning research, analytics, and trading tools.",
        public_path="/legal/financial-disclaimer.html",
    ),
    "risk-disclosure": LegalDocument(
        key="risk-disclosure",
        title="Risk Disclosure",
        filename="risk-disclosure.html",
        category="Financial Disclosures",
        summary="Investment, trading, market, model, operational, and technology risks.",
        public_path="/legal/risk-disclosure.html",
    ),
    "ai-disclosure": LegalDocument(
        key="ai-disclosure",
        title="AI Disclosure",
        filename="ai-disclosure.html",
        category="Financial Disclosures",
        summary="AI limitations, probabilistic outputs, and human-review responsibilities.",
        public_path="/legal/ai-disclosure.html",
    ),
    "market-data-disclaimer": LegalDocument(
        key="market-data-disclaimer",
        title="Market Data Disclaimer",
        filename="market-data-disclaimer.html",
        category="Financial Disclosures",
        summary="Third-party data ownership, delays, corrections, and licensing restrictions.",
        public_path="/legal/market-data-disclaimer.html",
    ),
    "acceptable-use-policy": LegalDocument(
        key="acceptable-use-policy",
        title="Acceptable Use Policy",
        filename="acceptable-use-policy.html",
        category="Platform Policies",
        summary="Rules governing lawful, secure, and responsible use of AIQ Intellus.",
        public_path="/legal/acceptable-use-policy.html",
    ),
    "api-license": LegalDocument(
        key="api-license",
        title="API License",
        filename="api-license.html",
        category="Platform Policies",
        summary="Developer terms for API authentication, usage, rate limits, and versioning.",
        public_path="/legal/api-license.html",
    ),
    "security": LegalDocument(
        key="security",
        title="Security Statement",
        filename="security.html",
        category="Trust & Security",
        summary="Security controls, operational safeguards, and responsible disclosure.",
        public_path="/legal/security.html",
    ),
    "accessibility": LegalDocument(
        key="accessibility",
        title="Accessibility Statement",
        filename="accessibility.html",
        category="Trust & Security",
        summary="Accessibility goals, standards, feedback, and support.",
        public_path="/legal/accessibility.html",
    ),
    "contact": LegalDocument(
        key="contact",
        title="Legal Contact",
        filename="contact.html",
        category="Support",
        summary="Legal, privacy, security, accessibility, and support contact information.",
        public_path="/legal/contact.html",
    ),
}


def get_document(key: str) -> LegalDocument:
    normalized = (key or "").strip().lower()
    return DOCUMENTS.get(normalized, DOCUMENTS["privacy-policy"])


def iter_documents(category: Optional[str] = None) -> Iterable[LegalDocument]:
    docs = DOCUMENTS.values()
    if category:
        docs = [doc for doc in docs if doc.category == category]
    return sorted(docs, key=lambda doc: (doc.category, doc.title))


def categories() -> list[str]:
    return sorted({doc.category for doc in DOCUMENTS.values()})
