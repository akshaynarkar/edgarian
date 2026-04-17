"""
/company/{ticker}/signals — full Edgarian output contract.

Pulls two filings, extracts XBRL metrics, diffs sections with per-section
timeouts, runs the flag engine, and returns the structured signal dict.

Query params:
  form    — "10-K" (default) or "10-Q"
  fast    — if "true", skip section diffs entirely (metrics + flags only, ~2s)

Option B fix (April 2026):
  _parse_obj() now has its own generous timeout (_OBJ_TIMEOUT = 120s) so that
  large filings (RTX, Boeing, JPM) are fully loaded before the per-section diff
  clock starts. Previously the 25s _SECTION_TIMEOUT fired during obj() itself,
  yielding chars_extracted=0 and no text-based flags.

  _SECTION_TIMEOUT raised to 90s — after obj() is loaded, text extraction is
  fast (~1-2s per section); this headroom is for the diff computation on very
  large sections (RTX Item 1A is ~98K chars).
"""

from __future__ import annotations

import concurrent.futures
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

from core.diff import diff_sections
from core.edgar_client import (
    filing_meta,
    filing_period,
    get_company,
    get_two_filings,
    safe_xbrl,
)
from core.filing_cleaner import extract_section
from core.flags import evaluate_flags
from core.metrics import build_metrics_diff, extract_metrics
from core.owner_earnings import compute_owner_earnings

router = APIRouter(prefix="/company", tags=["signals"])

# Map our section keys to TenK __getitem__ format
_SECTION_ITEM_MAP = {
    "1A": "Item 1A",
    "7":  "Item 7",
    "8":  "Item 8",
    "1":  "Item 1",
}

# Cap per section to avoid huge memory / diff time on monster filings
_SECTION_CHAR_LIMITS: Dict[str, int] = {
    "1A": 500_000,
    "7":  500_000,
    "8":  120_000,
}
_DEFAULT_CHAR_LIMIT = 300_000

# --- KEY TIMEOUTS ---
# obj() timeout: large filings (RTX, Boeing) take 30-40s to parse.
# Must complete before section diff clock starts.
_OBJ_TIMEOUT = 120   # seconds — generous, obj() must fully load

# Section diff timeout: after obj() is loaded, extraction + diff is fast.
# Raised from 25s → 90s to handle very large sections (RTX 1A = 98K chars).
_SECTION_TIMEOUT = 90


_PROP_MAP = {
    "Item 1A": "risk_factors",
    "Item 7":  "management_discussion",
    "Item 1":  "business",
}


def _get_section_text(obj: Any, filing: Any, section: str) -> str:
    """
    Extract section text using native edgartools TenK API.
    Accepts a pre-parsed obj to avoid redundant .obj() calls.
    Strategy: bracket operator → named property → raw HTML fallback.
    """
    item_key = _SECTION_ITEM_MAP.get(section, f"Item {section}")
    limit = _SECTION_CHAR_LIMITS.get(section, _DEFAULT_CHAR_LIMIT)

    # Strategy 1: bracket operator (edgartools v5.29 native)
    try:
        text = obj[item_key]
        if text and isinstance(text, str) and len(text) > 100:
            return text[:limit]
    except Exception:
        pass

    # Strategy 2: named properties
    prop = _PROP_MAP.get(item_key)
    if prop:
        try:
            text = getattr(obj, prop, None)
            if text and isinstance(text, str) and len(text) > 100:
                return text[:limit]
        except Exception:
            pass

    # Strategy 3: raw HTML → filing_cleaner
    try:
        raw_html = filing.html() if hasattr(filing, "html") else None
        if not raw_html:
            raw_html = getattr(obj, "_filing", filing).html()
        if raw_html:
            return extract_section(raw_html, section)[:limit]
    except Exception:
        pass

    return ""


def _diff_section_timed(
    current_obj: Any,
    prior_obj: Any,
    current_filing: Any,
    prior_filing: Any,
    section: str,
    filing_url: str,
) -> dict:
    """
    Extract + diff one section with a timeout.
    obj() is already parsed and passed in — timeout here covers only
    text extraction + diff computation, not filing parsing.
    """
    empty: dict = {
        "added": [], "removed": [], "modified": [],
        "truncated": False, "chars_extracted": 0,
        "filing_url": filing_url,
    }

    def _extract_and_diff():
        current_text = _get_section_text(current_obj, current_filing, section)
        prior_text   = _get_section_text(prior_obj, prior_filing, section)
        if not current_text or not prior_text:
            return empty
        limit = _SECTION_CHAR_LIMITS.get(section, _DEFAULT_CHAR_LIMIT)
        truncated = len(current_text) >= limit or len(prior_text) >= limit
        result = diff_sections(current_text, prior_text)
        result["truncated"] = truncated
        result["chars_extracted"] = len(current_text)
        result["filing_url"] = filing_url if truncated else ""
        return result

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(_extract_and_diff)
            return future.result(timeout=_SECTION_TIMEOUT)
    except concurrent.futures.TimeoutError:
        timed_out = dict(empty)
        timed_out["truncated"] = True
        timed_out["timed_out"] = True
        timed_out["filing_url"] = filing_url
        return timed_out
    except Exception:
        return empty


def _parse_obj_with_timeout(filing: Any, timeout: int = _OBJ_TIMEOUT) -> Optional[Any]:
    """
    Parse filing.obj() with an explicit timeout.
    Returns None if parsing fails or exceeds timeout.
    Large filings (RTX) take 30-40s — _OBJ_TIMEOUT must cover this.
    """
    def _do_parse():
        try:
            return filing.obj()
        except Exception:
            return None

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(_do_parse)
            return future.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        return None
    except Exception:
        return None


@router.get("/{ticker}/signals")
def get_signals(ticker: str, form: str = "10-K", fast: str = "false") -> Dict[str, Any]:
    """
    Return the full Edgarian signal dict for *ticker*.

    Query params:
      form  — "10-K" (default) or "10-Q"
      fast  — "true" skips section diffs (metrics + flags only, ~2s)
    """
    skip_diffs = fast.lower() in ("true", "1", "yes")

    # 1. Fetch two filings
    try:
        current_filing, prior_filing = get_two_filings(ticker, form=form)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"EDGAR fetch failed: {exc}")

    current_period = filing_period(current_filing)
    prior_period   = filing_period(prior_filing)
    meta           = filing_meta(current_filing)

    # 2. Section diffs (skipped in fast mode)
    empty_diff = {
        "added": [], "removed": [], "modified": [],
        "truncated": False, "chars_extracted": 0, "filing_url": meta["filing_url"],
    }

    if skip_diffs:
        section_diffs = {
            "risk_factors": {**empty_diff, "skipped": True},
            "mda":          {**empty_diff, "skipped": True},
            "revenue_rec":  {**empty_diff, "skipped": True},
        }
    else:
        filing_url = meta["filing_url"]

        # --- OPTION B FIX ---
        # Parse both filing objects in parallel with _OBJ_TIMEOUT (120s).
        # This must fully complete before section diff timeouts start.
        # Previously obj() had no timeout and consumed the section budget.
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            f_current = pool.submit(_parse_obj_with_timeout, current_filing)
            f_prior   = pool.submit(_parse_obj_with_timeout, prior_filing)
            current_obj = f_current.result()  # blocks until done or 120s
            prior_obj   = f_prior.result()

        if current_obj is None or prior_obj is None:
            # obj() failed or timed out — fall back to graceful empty diffs
            section_diffs = {
                "risk_factors": {**empty_diff, "timed_out": True, "truncated": True},
                "mda":          {**empty_diff, "timed_out": True, "truncated": True},
                "revenue_rec":  {**empty_diff, "timed_out": True, "truncated": True},
            }
        else:
            # obj() is fully loaded — now run section diffs in parallel.
            # _SECTION_TIMEOUT (90s) covers text extraction + diff only.
            sections     = ["1A", "7", "8"]
            section_keys = ["risk_factors", "mda", "revenue_rec"]
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
                futures = {
                    key: pool.submit(
                        _diff_section_timed,
                        current_obj, prior_obj,
                        current_filing, prior_filing,
                        sec, filing_url
                    )
                    for key, sec in zip(section_keys, sections)
                }
                section_diffs = {key: fut.result() for key, fut in futures.items()}

    # 3. XBRL metrics
    current_xbrl = safe_xbrl(current_filing)
    prior_xbrl   = safe_xbrl(prior_filing)
    current_raw  = extract_metrics(current_xbrl)
    prior_raw    = extract_metrics(prior_xbrl)
    metrics_diff = build_metrics_diff(current_raw, prior_raw)

    # Append owner earnings
    try:
        if current_xbrl and prior_xbrl:
            oe = compute_owner_earnings(
                current_xbrl.statements.cash_flow_statement(),
                prior_xbrl.statements.cash_flow_statement(),
            )
            if oe.value is not None:
                metrics_diff.append({
                    "metric": "Owner Earnings",
                    "prior": None,
                    "current": oe.value,
                    "change_pct": oe.yoy_change_pct,
                })
    except Exception:
        pass

    # 4. Red flags
    red_flags = evaluate_flags(metrics_diff, section_diffs)

    # 5. Company name
    try:
        company_name = getattr(get_company(ticker), "name", ticker.upper())
    except Exception:
        company_name = ticker.upper()

    return {
        "company":           company_name,
        "ticker":            ticker.upper(),
        "filing_type":       form,
        "current_period":    current_period,
        "prior_period":      prior_period,
        "accession_number":  meta["accession_number"],
        "cik":               meta["cik"],
        "filing_url":        meta["filing_url"],
        "document_url":      meta["document_url"],
        "fast_mode":         skip_diffs,
        "metrics_diff":      metrics_diff,
        "section_diffs":     section_diffs,
        "red_flags":         red_flags,
    }
