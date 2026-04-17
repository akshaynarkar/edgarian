"""Form 4 insider cluster detection."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, List

import pandas as pd
import yfinance as yf


def classify_price_vs_52wk(ticker: str, price: float) -> str:
    history = yf.Ticker(ticker).history(period="1y")
    if history.empty:
        return "mid"
    high = float(history["High"].max())
    low = float(history["Low"].min())
    if high <= low:
        return "mid"
    band = (high - low) * 0.2
    if price <= low + band:
        return "near_low"
    if price >= high - band:
        return "near_high"
    return "mid"


def detect_cluster_buys(transactions: pd.DataFrame) -> List[bool]:
    buys = transactions[transactions["type"].str.upper() == "BUY"].copy()
    buys["date"] = pd.to_datetime(buys["date"])
    cluster_flags = []
    for _, row in buys.iterrows():
        window_start = row["date"] - timedelta(days=30)
        window = buys[(buys["date"] >= window_start) & (buys["date"] <= row["date"])]
        cluster_flags.append(window["name"].nunique() >= 3)
    return cluster_flags


def get_insider_activity(company: Any, ticker: str, limit: int = 20) -> Dict[str, Any]:
    filings = company.get_filings(form="4").head(limit)
    rows: List[dict] = []
    for filing in filings:
        try:
            form4 = filing.obj()
            df = getattr(form4, "transactions", None)
            if df is None or len(df) == 0:
                continue
            frame = df.copy()
            frame.columns = [str(col).lower() for col in frame.columns]
            for _, row in frame.iterrows():
                tx_type = str(row.get("type") or row.get("transaction_type") or "").upper()
                shares = float(row.get("shares") or row.get("transaction_shares") or 0)
                price = float(row.get("price") or row.get("transaction_price") or 0)
                rows.append(
                    {
                        "name": row.get("name") or row.get("reporting_owner_name") or "Unknown",
                        "title": row.get("title") or row.get("officer_title") or "",
                        "type": "BUY" if "BUY" in tx_type or tx_type == "P" else "SELL",
                        "shares": shares,
                        "price": price,
                        "date": str(pd.to_datetime(row.get("date") or row.get("transaction_date")).date()),
                        "pct_of_holdings": row.get("pct_of_holdings"),
                    }
                )
        except Exception:
            continue

    if not rows:
        return {"transactions": [], "cluster_flag": False}

    tx = pd.DataFrame(rows)
    buy_mask = tx["type"] == "BUY"
    tx.loc[buy_mask, "cluster"] = detect_cluster_buys(tx[buy_mask].copy())
    tx["cluster"] = tx["cluster"].fillna(False)
    tx["price_vs_52wk"] = tx["price"].apply(lambda p: classify_price_vs_52wk(ticker, float(p)))
    return {
        "transactions": tx.to_dict(orient="records"),
        "cluster_flag": bool(tx["cluster"].any()),
    }
