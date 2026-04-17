"""Peer universe and percentile ranking helpers."""

from __future__ import annotations

from statistics import median
from typing import Any, Dict, Iterable, List, Optional

import yfinance as yf

from .owner_earnings import compute_owner_earnings


def percentile_rank(value: float, population: List[float]) -> int:
    if not population:
        return 0
    below = sum(1 for x in population if x <= value)
    return round((below / len(population)) * 100)


def get_industry_label(ticker: str) -> Optional[str]:
    try:
        info = yf.Ticker(ticker).info
        return info.get("industry") or info.get("sector")
    except Exception:
        return None


def build_peer_metrics(subject_ticker: str, subject_company: Any, peer_companies: Iterable[Any]) -> Dict[str, Any]:
    industry = get_industry_label(subject_ticker)
    sic = getattr(subject_company, "sic", None) or getattr(subject_company, "sic_code", None)

    peer_rows: List[dict] = []
    for company in peer_companies:
        try:
            ticker = getattr(company, "ticker", None) or getattr(company, "symbol", None)
            if not ticker:
                continue
            filings = company.get_filings(form="10-K")
            filing = filings[0]
            xbrl = filing.xbrl()
            if xbrl is None:
                continue
            owner = compute_owner_earnings(xbrl.statements.cash_flow_statement())
            peer_rows.append(
                {
                    "ticker": ticker,
                    "owner_earnings": owner.value,
                }
            )
        except Exception:
            continue

    subject_owner = None
    try:
        filings = subject_company.get_filings(form="10-K")
        xbrl = filings[0].xbrl()
        if xbrl is not None:
            subject_owner = compute_owner_earnings(xbrl.statements.cash_flow_statement()).value
    except Exception:
        pass

    owner_values = [row["owner_earnings"] for row in peer_rows if row["owner_earnings"] is not None]
    rankings = []
    if subject_owner is not None:
        rankings.append({"metric": "Owner Earnings", "value": subject_owner, "percentile": percentile_rank(subject_owner, owner_values)})

    return {
        "ticker": subject_ticker,
        "sector": industry,
        "sic": str(sic) if sic is not None else None,
        "peer_count": len(peer_rows),
        "peers": [row["ticker"] for row in peer_rows],
        "rankings": rankings,
    }
