from __future__ import annotations

from fastapi import APIRouter, HTTPException

from core.edgar_client import get_company, safe_xbrl
from core.metrics import _stmt_to_df  # shared helper

router = APIRouter(prefix="/company", tags=["financials"])


@router.get("/{ticker}/financials")
def financials(ticker: str):
    try:
        company = get_company(ticker)
        filings = company.get_filings(form="10-K")
        if len(filings) == 0:
            raise HTTPException(status_code=404, detail="No 10-K filings found")
        xbrl = safe_xbrl(filings[0])
        if xbrl is None:
            raise HTTPException(status_code=404, detail="No XBRL available for latest filing")

        income = _stmt_to_df(xbrl.statements.income_statement())
        if income is not None:
            return income.fillna("").to_dict(orient="index")
        return {"message": "Income statement loaded but could not convert to dict"}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
