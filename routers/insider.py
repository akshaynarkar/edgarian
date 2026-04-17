from __future__ import annotations

from fastapi import APIRouter, HTTPException

from core.edgar_client import get_company
from core.insider_cluster import get_insider_activity

router = APIRouter(prefix="/company", tags=["insider"])


@router.get("/{ticker}/insider")
def insider_activity(ticker: str, limit: int = 20):
    try:
        company = get_company(ticker)
        return get_insider_activity(company, ticker, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
