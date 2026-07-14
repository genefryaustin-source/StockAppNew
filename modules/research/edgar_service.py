"""
modules/research/edgar_service.py

Real SEC filing access via edgartools (https://github.com/dgunning/edgartools,
MIT license) -- full-text filing search, financial statement extraction
(10-K/10-Q), and filing metadata, straight from SEC EDGAR rather than only
through paid fundamentals providers. Complements modules.valuation and
Research Reports with primary-source filing data.

SEC's fair-access policy requires every requester to identify themselves
with a "Name email@domain.com"-style User-Agent on every request -- this
is not optional and isn't a secret, but it IS required, so it's resolved
through the same tenant-key system as every other provider
(SEC_EDGAR_IDENTITY) rather than hardcoded.

HONESTY NOTE: edgartools' class/method surface here (Company, get_filings,
latest_tenk, income_statement, etc.) was verified against the installed
package directly, but live SEC EDGAR network calls were NOT exercised in
the environment this was built in (no network path to sec.gov). Every
function degrades to {"available": False, "reason": ...} rather than
raising, but validate against a real filing before depending on exact
field names in production.
"""

from __future__ import annotations

from typing import Optional

_identity_set = False


def _ensure_identity(db=None, tenant_id: Optional[str] = None) -> Optional[str]:
    global _identity_set
    from modules.admin.tenant_api_keys import get_provider_key
    identity = get_provider_key("SEC_EDGAR_IDENTITY", db=db, tenant_id=tenant_id)
    if not identity:
        return None
    if not _identity_set:
        import edgar
        edgar.set_identity(identity)
        _identity_set = True
    return identity


def edgar_available(db=None, tenant_id: Optional[str] = None) -> bool:
    try:
        import edgar  # noqa: F401
    except Exception:
        return False
    return _ensure_identity(db=db, tenant_id=tenant_id) is not None


def get_company_filings(
    ticker: str, form_types: Optional[list[str]] = None, limit: int = 10,
    db=None, tenant_id: Optional[str] = None,
) -> dict:
    """Recent filings for a ticker, optionally filtered by form type
    (e.g. ["10-K", "10-Q", "8-K"])."""
    if not _ensure_identity(db=db, tenant_id=tenant_id):
        return {"available": False, "reason": "SEC_EDGAR_IDENTITY isn't configured "
                                                "(Admin > API Keys) -- SEC requires a contact identity on every request."}
    try:
        import edgar
        company = edgar.Company(ticker)
        filings = company.get_filings(form=form_types) if form_types else company.get_filings()
        rows = []
        for f in filings.head(limit) if hasattr(filings, "head") else list(filings)[:limit]:
            rows.append({
                "form": getattr(f, "form", None),
                "filing_date": str(getattr(f, "filing_date", "")),
                "accession_no": getattr(f, "accession_no", None),
                "url": getattr(f, "filing_url", None) or getattr(f, "document_url", None),
            })
        return {"available": True, "ticker": ticker.upper(), "filings": rows}
    except Exception as e:
        return {"available": False, "reason": f"EDGAR lookup failed for {ticker}: {e}"}


def get_latest_10k_summary(ticker: str, db=None, tenant_id: Optional[str] = None) -> dict:
    """Key figures from the most recent 10-K: revenue, net income, total
    assets/liabilities where available."""
    if not _ensure_identity(db=db, tenant_id=tenant_id):
        return {"available": False, "reason": "SEC_EDGAR_IDENTITY isn't configured (Admin > API Keys)."}
    try:
        import edgar
        company = edgar.Company(ticker)
        tenk = company.latest_tenk
        if tenk is None:
            return {"available": False, "reason": f"No 10-K found for {ticker}."}

        financials = getattr(tenk, "financials", None) or company.get_financials()
        income = getattr(financials, "income_statement", None)
        balance = getattr(financials, "balance_sheet", None)

        return {
            "available": True,
            "ticker": ticker.upper(),
            "filing_date": str(getattr(tenk, "filing_date", "")),
            "period_of_report": str(getattr(tenk, "period_of_report", "")),
            "revenue_ttm": company.get_ttm_revenue() if hasattr(company, "get_ttm_revenue") else None,
            "net_income_ttm": company.get_ttm_net_income() if hasattr(company, "get_ttm_net_income") else None,
            "has_income_statement": income is not None,
            "has_balance_sheet": balance is not None,
            "filing_url": getattr(tenk, "filing_url", None),
        }
    except Exception as e:
        return {"available": False, "reason": f"10-K summary failed for {ticker}: {e}"}


def full_text_search(query: str, form_types: Optional[list[str]] = None, limit: int = 10,
                      db=None, tenant_id: Optional[str] = None) -> dict:
    """SEC's full-text search across all filers -- useful for finding which
    companies mention a specific term (product, risk factor, litigation) in
    recent filings."""
    if not _ensure_identity(db=db, tenant_id=tenant_id):
        return {"available": False, "reason": "SEC_EDGAR_IDENTITY isn't configured (Admin > API Keys)."}
    try:
        import edgar
        results = edgar.get_filings(form=form_types) if form_types else edgar.get_filings()
        # edgartools' full-text search API surface varies by version --
        # fall back to a clear "not supported" rather than guessing at a
        # method name that may not exist in the installed version.
        if hasattr(edgar, "EFTSSearch") or hasattr(results, "search"):
            search_results = results.search(query) if hasattr(results, "search") else edgar.EFTSSearch(query)
            rows = [{"form": getattr(r, "form", None), "entity": getattr(r, "entity", None),
                     "filed": str(getattr(r, "filing_date", ""))} for r in list(search_results)[:limit]]
            return {"available": True, "query": query, "results": rows}
        return {"available": False, "reason": "Full-text search API not found in this edgartools version."}
    except Exception as e:
        return {"available": False, "reason": f"Full-text search failed: {e}"}
