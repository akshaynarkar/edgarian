from __future__ import annotations

from fastapi import APIRouter, HTTPException

from core.edgar_client import get_company
from core.peer_metrics import build_peer_metrics

router = APIRouter(prefix="/company", tags=["peers"])


@router.get("/{ticker}/peers")
def peer_metrics(ticker: str):
    try:
        company = get_company(ticker)
        # Peer universe via same-SIC discovery is Phase 2.
        # Returns subject metrics + empty peer set until then.
        return build_peer_metrics(ticker, company, [])
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
