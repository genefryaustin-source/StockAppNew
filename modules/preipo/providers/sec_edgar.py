# ============================================================
# modules/preipo/providers/sec_edgar.py
# SEC EDGAR public filing provider
# ============================================================

from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, UTC, timedelta
from typing import Any, Dict, List, Optional

import requests

SEC_COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_CURRENT_ATOM_URL = "https://www.sec.gov/cgi-bin/browse-edgar"
#SEC_CURRENT_ATOM_URL = "https://www.sec.gov/Archives/edgar/daily-index/or https://data.sec.gov/submissions/""
DEFAULT_TIMEOUT = (10, 45)

IPO_FORMS = {
    "S-1",
    "S-1/A",
    "F-1",
    "F-1/A",
    "424B4",
    "424B1",
    "424B3",
    "S-4",
    "S-4/A",
}

DISCOVERY_FORMS = [
    "S-1",
    "S-1/A",
    "F-1",
    "F-1/A",
    "424B4",
    "424B3",
    "S-4",
    "S-4/A",
]

SPAC_KEYWORDS = (
    "acquisition corp",
    "acquisition corporation",
    "acquisition company",
    "blank check",
    "spac",
    "special purpose acquisition",
)


_USER_AGENT = (
    "Conduro Ventures LLC "
    "info@conduroventures.com"
)


def _headers(host=None):
    return {
        "User-Agent": _USER_AGENT,
        "Accept": "application/json,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    }


def _parse_date(value: Any):
    if not value:
        return None
    try:
        text = str(value).strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text.replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    except Exception:
        try:
            return datetime.strptime(str(value)[:10], "%Y-%m-%d").replace(tzinfo=UTC)
        except Exception:
            return None


def _normalized_name(value: Any) -> str:
    return str(value or "").strip().upper()


def _detect_spac(company_name: str, form_type: Optional[str] = None, summary: Optional[str] = None) -> bool:
    text = " ".join(
        part for part in [company_name or "", form_type or "", summary or ""] if part
    ).lower()
    return any(keyword in text for keyword in SPAC_KEYWORDS)


def _extract_company_from_atom_title(title: str, fallback_form: Optional[str] = None) -> str:
    text = str(title or "").strip()
    if " - " in text:
        parts = text.split(" - ", 1)
        if parts[0].strip().upper() in IPO_FORMS:
            text = parts[1].strip()
    text = re.sub(r"\s*\(.*?CIK\s*\d+.*?\)\s*", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"\s*\(.*?\)\s*$", "", text).strip()
    return text or "Unknown"


def _extract_cik(*values: Any) -> Optional[str]:
    for value in values:
        text = str(value or "")
        match = re.search(r"CIK\s*(\d+)", text, flags=re.IGNORECASE)
        if match:
            return match.group(1).zfill(10)
        match = re.search(r"/data/(\d+)/", text)
        if match:
            return match.group(1).zfill(10)
    return None


def _extract_accession_from_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    match = re.search(r"/(\d{18})/", url)
    if match:
        raw = match.group(1)
        return f"{raw[0:10]}-{raw[10:12]}-{raw[12:]}"
    match = re.search(r"(\d{10}-\d{2}-\d{6})", url)
    if match:
        return match.group(1)
    return None


def search_sec_company_index(query: str, limit: int = 25) -> List[Dict[str, Any]]:
    if not query:
        return []
    time.sleep(0.5)
    r = requests.get(
        SEC_COMPANY_TICKERS_URL,
        headers=_headers(),
        timeout=DEFAULT_TIMEOUT,
    )
    r.raise_for_status()
    data = r.json()

    q = query.lower().strip()
    results = []
    for item in data.values():
        title = str(item.get("title") or "")
        ticker = str(item.get("ticker") or "")
        if q in title.lower() or q == ticker.lower():
            cik = str(item.get("cik_str") or "").zfill(10)
            results.append({
                "company_name": title,
                "ticker": ticker,
                "cik": cik,
            })
            if len(results) >= limit:
                break
    return results


def fetch_recent_ipo_filings_for_cik(
    cik: str,
    company_name: Optional[str] = None,
) -> List[Dict[str, Any]]:
    cik = str(cik).zfill(10)
    url = SEC_SUBMISSIONS_URL.format(cik=cik)
    time.sleep(0.5)
    r = requests.get(url, headers=_headers("data.sec.gov"), timeout=DEFAULT_TIMEOUT)
    r.raise_for_status()
    payload = r.json()
    print("URL:", url)
    print("STATUS:", r.status_code)
    print("TEXT:", r.text[:1000])
    company = company_name or payload.get("name") or "Unknown"
    recent = payload.get("filings", {}).get("recent", {})
    forms = recent.get("form") or []
    dates = recent.get("filingDate") or []
    accessions = recent.get("accessionNumber") or []
    primary_docs = recent.get("primaryDocument") or []

    rows = []
    for form, date, accession, doc in zip(forms, dates, accessions, primary_docs):
        if form not in IPO_FORMS:
            continue

        accession_nodash = str(accession).replace("-", "")
        filing_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_nodash}/{doc}"
        rows.append({
            "company_name": company,
            "normalized_name": company.upper().strip(),
            "cik": cik,
            "filing_type": form,
            "filing_date": _parse_date(date),
            "accession_number": accession,
            "filing_url": filing_url,
            "is_spac": _detect_spac(company, form),
            "source": "SEC_EDGAR",
            "raw_payload": {
                "cik": cik,
                "form": form,
                "filingDate": date,
                "accessionNumber": accession,
                "primaryDocument": doc,
            },
        })
    return rows


def _fetch_current_form_feed(form_type: str, count: int = 100) -> List[Dict[str, Any]]:

    params = {
        "action": "getcurrent",
        "type": form_type,
        "owner": "exclude",
        "count": max(int(count), 100),
        "output": "atom",
    }
    time.sleep(0.5)
    response = requests.get(
        SEC_CURRENT_ATOM_URL,
        params=params,
        headers=_headers(),
        timeout=DEFAULT_TIMEOUT,
    )
    time.sleep(0.5)
    print(response.text[:500])
    response.raise_for_status()

    print("=" * 80)
    print("SEC URL:", response.url)
    print("STATUS:", response.status_code)
    print("CONTENT LENGTH:", len(response.text))
    print("=" * 80)

    root = ET.fromstring(response.content)

    ns = {
        "atom": "http://www.w3.org/2005/Atom"
    }

    rows: List[Dict[str, Any]] = []

    entries = root.findall("atom:entry", ns)

    print(
        f"FORM {form_type} ENTRIES:",
        len(entries)
    )

    for entry in entries:

        title = entry.findtext(
            "atom:title",
            default="",
            namespaces=ns,
        )

        updated = entry.findtext(
            "atom:updated",
            default="",
            namespaces=ns,
        )

        summary = entry.findtext(
            "atom:summary",
            default="",
            namespaces=ns,
        )

        link_node = entry.find(
            "atom:link",
            ns,
        )

        filing_url = (
            link_node.attrib.get("href")
            if link_node is not None
            else None
        )

        company_name = _extract_company_from_atom_title(
            title,
            form_type,
        )

        filing_date = _parse_date(updated)

        cik = _extract_cik(
            title,
            summary,
            filing_url,
        )

        accession = _extract_accession_from_url(
            filing_url
        )

        rows.append({
            "company_name": company_name,
            "normalized_name": _normalized_name(company_name),
            "cik": cik,
            "filing_type": form_type,
            "filing_date": filing_date,
            "accession_number": accession
                or f"{form_type}:{cik or company_name}:{updated}",
            "filing_url": filing_url,
            "is_spac": _detect_spac(
                company_name,
                form_type,
                summary,
            ),
            "source": "SEC_EDGAR_DISCOVERY",
            "raw_payload": {
                "title": title,
                "updated": updated,
                "summary": summary,
                "link": filing_url,
                "form": form_type,
                "cik": cik,
            },
        })

    return rows


def fetch_recent_ipo_candidates(
    days: int = 90,
    forms: Optional[List[str]] = None,
    count_per_form: int = 100,
    sleep_seconds: float = 0.15,
) -> List[Dict[str, Any]]:
    """
    Discover recent IPO/SPAC candidates from SEC EDGAR's current filings feed.

    This does not require the user to know a company name. It scans recent form
    feeds for S-1, F-1, 424B and S-4 filings, then normalizes each filing for
    the Pre-IPO Discovery page.
    """

    cutoff = datetime.now(UTC) - timedelta(days=max(int(days), 1))
    target_forms = forms or DISCOVERY_FORMS
    discovered: List[Dict[str, Any]] = []
    seen = set()

    for form_type in target_forms:

        print("=" * 80)
        print("SEC FORM:", form_type)

        try:
            rows = _fetch_current_form_feed(
                form_type,
                count=count_per_form
            )

            print(
                f"RAW {form_type}:",
                len(rows)
            )

        except Exception as exc:

            print(
                f"[SEC DISCOVERY] {form_type} failed:",
                exc
            )

            rows = []

        accepted = 0

        for row in rows:

            filing_date = row.get("filing_date")

            #if filing_date is not None and filing_date < cutoff:
                #continue

            accepted += 1
            print(
                f"ACCEPTED {form_type}:",
                accepted
            )
            key = (
                row.get("accession_number"),
                row.get("normalized_name"),
                row.get("filing_type"),
                row.get("filing_date"),
            )
            if key in seen:
                continue
            seen.add(key)
            discovered.append(row)

        if sleep_seconds:
            time.sleep(sleep_seconds)

    discovered.sort(key=lambda r: r.get("filing_date") or datetime.min.replace(tzinfo=UTC), reverse=True)
    return discovered
