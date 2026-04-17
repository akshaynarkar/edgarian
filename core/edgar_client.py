"""
Thin wrapper around edgartools Company + Filing access.

Centralises set_identity(), error handling, and filing pair retrieval
so all routers import from one place.
"""

from __future__ import annotations

import os
from typing import Any, Optional, Tuple

_IDENTITY_SET = False


def _ensure_identity() -> None:
    global _IDENTITY_SET
    if _IDENTITY_SET:
        return
    from edgar import set_identity
    identity = os.getenv("EDGAR_IDENTITY", "edgarian@edgarian.dev")
    set_identity(identity)
    _IDENTITY_SET = True


def get_company(ticker: str) -> Any:
    """Return an edgartools Company object for *ticker*."""
    _ensure_identity()
    from edgar import Company
    return Company(ticker.upper())


def get_two_filings(
    ticker: str,
    form: str = "10-K",
) -> Tuple[Any, Any]:
    """
    Return (current_filing, prior_filing) — the two most recent *form* filings.

    Both are raw Filing objects (not .obj()). Call .obj() downstream when you
    need the typed TenK/TenQ object, and .xbrl() for XBRL data.

    Raises:
        ValueError: if fewer than 2 filings are available.
    """
    company = get_company(ticker)
    filings = company.get_filings(form=form)
    if len(filings) < 2:
        raise ValueError(
            f"Need at least 2 {form} filings for {ticker}, found {len(filings)}"
        )
    return filings[0], filings[1]


def safe_xbrl(filing: Any) -> Optional[Any]:
    """Return the XBRL object for *filing*, or None if unavailable."""
    try:
        xbrl = filing.xbrl()
        return xbrl
    except Exception:
        return None


def filing_period(filing: Any) -> Optional[str]:
    """Return the filing period date as an ISO string, or None."""
    for attr in ("period_of_report", "period", "date"):
        val = getattr(filing, attr, None)
        if val:
            return str(val)
    return None


def filing_meta(filing: Any) -> dict:
    """
    Return accession number, CIK, and EDGAR URLs for a filing.

    filing_url  — the SEC EDGAR filing index page (human-readable)
    document_url — base URL for filing documents (useful for deep links)
    """
    accession = getattr(filing, "accession_no", None) or getattr(filing, "accession_number", None) or ""
    cik = getattr(filing, "cik", None) or ""
    accession_clean = accession.replace("-", "") if accession else ""

    filing_url = (
        f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession}-index.html"
        if accession and cik else ""
    )
    document_url = (
        f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_clean}/"
        if accession_clean and cik else ""
    )
    return {
        "accession_number": accession,
        "cik": str(cik),
        "filing_url": filing_url,
        "document_url": document_url,
    }
