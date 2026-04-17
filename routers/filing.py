from __future__ import annotations

from fastapi import APIRouter, HTTPException

from core.edgar_client import filing_meta, get_company

router = APIRouter(prefix="/company", tags=["filing"])

_SECTION_ITEM_MAP = {
    "1": "Item 1", "1A": "Item 1A", "1B": "Item 1B",
    "7": "Item 7", "7A": "Item 7A", "8": "Item 8",
}

_SECTION_CHAR_LIMITS = {
    "1A": 500_000,
    "7":  500_000,
    "8":  120_000,
}
_DEFAULT_CHAR_LIMIT = 300_000


@router.get("/{ticker}/filing/{section}")
def filing_section(ticker: str, section: str):
    """
    Return section text for the most recent 10-K.

    Response includes:
      text          — section content (may be truncated)
      truncated     — True if text was cut at the char limit
      chars_extracted — how many chars were returned
      filing_url    — SEC EDGAR filing index URL (for full reading)
      document_url  — base URL for filing documents
    """
    try:
        company  = get_company(ticker)
        filings  = company.get_filings(form="10-K")
        if len(filings) == 0:
            raise HTTPException(status_code=404, detail="No 10-K filings found")

        filing   = filings[0]
        meta     = filing_meta(filing)
        obj      = filing.obj()
        sec_key  = section.upper().replace("ITEM", "").strip()
        item_key = _SECTION_ITEM_MAP.get(sec_key, f"Item {sec_key}")
        limit    = _SECTION_CHAR_LIMITS.get(sec_key, _DEFAULT_CHAR_LIMIT)

        text = None
        try:
            text = obj[item_key]
        except Exception:
            pass

        if not text:
            _PROPS = {
                "Item 1A": "risk_factors",
                "Item 7":  "management_discussion",
                "Item 1":  "business",
            }
            prop = _PROPS.get(item_key)
            if prop:
                text = getattr(obj, prop, None)

        text = text or ""
        truncated = len(text) > limit
        text = text[:limit]

        return {
            "ticker":          ticker.upper(),
            "section":         item_key,
            "text":            text,
            "truncated":       truncated,
            "chars_extracted": len(text),
            "filing_url":      meta["filing_url"],
            "document_url":    meta["document_url"],
            "accession_number": meta["accession_number"],
            "note": (
                f"Section truncated at {limit:,} chars. "
                f"View full filing at: {meta['filing_url']}"
                if truncated else ""
            ),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
