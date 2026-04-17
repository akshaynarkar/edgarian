from __future__ import annotations

from fastapi import APIRouter, HTTPException
from core.edgar_client import get_company, safe_xbrl
from core.metrics import extract_metrics

router = APIRouter(prefix="/company", tags=["financials"])

MAX_YEARS = 5


@router.get("/{ticker}/financials")
def financials(ticker: str):
    """
    Return up to 5 years of key financial metrics extracted from XBRL.

    Response shape:
    {
      "ticker": "AAPL",
      "periods": ["Sep '21", "Sep '22", "Sep '23", "Sep '24", "Sep '25"],
      "rows": {
        "Revenue":    [null, 365817000000, 383285000000, 391035000000, 416161000000],
        "Net Income": [...],
        ...
      }
    }
    Periods ordered oldest → newest. null = metric not found in that filing.
    """
    try:
        company = get_company(ticker)
        filings = company.get_filings(form="10-K")

        if len(filings) == 0:
            raise HTTPException(status_code=404, detail="No 10-K filings found")

        # Take up to MAX_YEARS filings (most-recent first from edgartools)
        selected = list(filings[:MAX_YEARS])

        results = []
        for filing in selected:
            xbrl = safe_xbrl(filing)
            metrics = extract_metrics(xbrl) if xbrl is not None else {}

            # Build human-readable period label
            period = (
                getattr(filing, "period_of_report", None)
                or getattr(filing, "filing_date", None)
            )
            try:
                from datetime import datetime
                dt = datetime.strptime(str(period)[:10], "%Y-%m-%d")
                label = dt.strftime("%b '%y")   # e.g. "Sep '24"
            except Exception:
                label = str(period)[:7] if period else "?"

            results.append({"label": label, "metrics": metrics})

        # Reverse to oldest → newest
        results = list(reversed(results))

        periods = [r["label"] for r in results]

        # Union of all metric keys, preserving order
        all_keys = list(dict.fromkeys(
            key for r in results for key in r["metrics"].keys()
        ))

        rows: dict[str, list] = {}
        for key in all_keys:
            values = [r["metrics"].get(key, None) for r in results]
            if any(v is not None for v in values):
                rows[key] = values

        return {
            "ticker": ticker.upper(),
            "periods": periods,
            "rows": rows,
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
