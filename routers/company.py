from __future__ import annotations

from fastapi import APIRouter, HTTPException

import yfinance as yf

from core.edgar_client import get_company

router = APIRouter(prefix="/company", tags=["company"])


@router.get("/{ticker}")
def company_info(ticker: str):
    try:
        company = get_company(ticker)
        info = {}
        try:
            info = yf.Ticker(ticker).info
        except Exception:
            pass
        return {
            "ticker": ticker.upper(),
            "name": getattr(company, "name", info.get("longName") or ticker.upper()),
            "cik": getattr(company, "cik", None),
            "sic": getattr(company, "sic", None) or getattr(company, "sic_code", None),
            "sector": info.get("sector"),
            "exchange": info.get("exchange"),
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
