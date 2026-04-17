"""
Extract key financial metrics from edgartools XBRL statements.

Produces the metrics_diff rows consumed by flags.py and the output contract.
Strategy: prefer StandardConcept labels (cross-company stable), fall back to
fuzzy label matching for metrics not yet in the StandardConcept enum
(SBC, CapEx, Shares Outstanding).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _stmt_to_df(stmt: Any) -> Optional[pd.DataFrame]:
    """
    Return a DataFrame with label as index and only numeric period columns.

    edgartools v5.29 returns flat DataFrames with metadata columns mixed in
    (concept, label, standard_concept, level, abstract, ...).
    We pivot on label and drop all non-numeric columns so _latest_value works.
    """
    if stmt is None:
        return None

    df = None
    for kwargs in ({"view": "standard", "standard": True}, {}):
        try:
            candidate = stmt.to_dataframe(**kwargs)
            if candidate is not None and not candidate.empty:
                df = candidate
                break
        except Exception:
            continue

    if df is None:
        return None

    # Use label column as index if present
    if "label" in df.columns:
        df = df.set_index("label")
        # Deduplicate: keep first occurrence of each label (top-level summary rows)
        df = df[~df.index.duplicated(keep="first")]

    # Drop known non-numeric metadata columns
    _META_COLS = {
        "concept", "standard_concept", "balance", "weight", "preferred_sign",
        "level", "abstract", "dimension", "is_breakdown", "dimension_axis",
        "dimension_member", "dimension_member_label", "dimension_label",
        "parent_concept", "parent_abstract_concept",
    }
    cols = [c for c in df.columns if c not in _META_COLS]
    df = df[cols]

    # Keep only columns with at least one numeric value
    numeric_cols = [
        c for c in df.columns
        if pd.to_numeric(df[c], errors="coerce").notna().any()
    ]
    if not numeric_cols:
        return None

    return df[numeric_cols]


def _latest_value(df: pd.DataFrame, label: str) -> Optional[float]:
    """
    Find *label* (case-insensitive substring match) in the DataFrame index
    and return the value from the most-recent period column.

    The DataFrame returned by edgartools has labels as the index and period
    dates as columns (most recent leftmost).
    """
    label_lower = label.lower()
    # Exact match first
    for idx in df.index:
        if str(idx).lower() == label_lower:
            return _first_numeric(df.loc[idx])
    # Substring match
    for idx in df.index:
        if label_lower in str(idx).lower():
            return _first_numeric(df.loc[idx])
    return None


def _first_numeric(row: pd.Series) -> Optional[float]:
    """Return the first non-null numeric value from a row (left = most recent)."""
    coerced = pd.to_numeric(row, errors="coerce")
    for val in coerced:
        if val is not None and not pd.isna(val):
            return float(val)
    return None


def _pct_change(prior: Optional[float], current: Optional[float]) -> Optional[float]:
    if prior is None or current is None or prior == 0:
        return None
    return round((current - prior) / abs(prior) * 100, 2)


def _metric_row(
    metric: str,
    prior: Optional[float],
    current: Optional[float],
    unit: str = "USD_thousands",
) -> dict:
    return {
        "metric": metric,
        "prior": prior,
        "current": current,
        "change_pct": _pct_change(prior, current),
        "unit": unit,
    }


# ---------------------------------------------------------------------------
# Revenue helpers — try multiple StandardConcept labels in order
# ---------------------------------------------------------------------------

_REVENUE_LABELS = [
    "Revenue",
    "Revenues",
    "Net Revenue",
    "Net Revenues",
    "Net Sales",
    "Total Revenue",
    "Total Revenues",
    "Contract Revenue",
    "Product Revenue",
]

_COGS_LABELS = [
    "Cost of Revenue",
    "Cost of Goods Sold",
    "Cost of Goods and Services Sold",
    "Cost of Sales",
    "Costs and Expenses",
]

_GROSS_PROFIT_LABELS = ["Gross Profit", "Gross Margin"]

# SBC, CapEx, D&A, Shares are not in StandardConcept — fuzzy match these
_SBC_LABELS = [
    "stock-based compensation",
    "share-based compensation",
    "stock based compensation",
    "share based compensation",
    "stock compensation expense",
]

_CAPEX_LABELS = [
    "capital expenditures",
    "purchases of property",
    "acquisition of property",
    "payments to acquire property",
    "capital spending",
]

_DA_LABELS = [
    "depreciation and amortization",
    "depreciation, amortization",
    "depreciation & amortization",
    "depreciation",
]

_SHARES_LABELS = [
    "common shares outstanding",
    "shares outstanding",
    "weighted average shares",
    "weighted-average shares",
    "diluted shares",
    "basic shares",
]

_RECEIVABLES_LABELS = [
    "accounts receivable",
    "trade receivables",
    "net receivables",
]

_GOODWILL_LABELS = [
    "goodwill",
    "goodwill, net",
]

_IMPAIRMENT_LABELS = [
    "goodwill impairment",
    "impairment of goodwill",
    "goodwill and intangible asset impairment",
    "asset impairment",
]

_LONG_TERM_DEBT_LABELS = [
    "long-term debt",
    "long term debt",
    "long-term debt, net",
    "notes payable",
    "long-term borrowings",
]

_OPERATING_CASHFLOW_LABELS = [
    "net cash from operating activities",
    "net cash provided by operating activities",
    "cash flows from operating activities",
    "operating activities",
]

_INVENTORY_LABELS = [
    "inventories",
    "inventory",
    "inventories, net",
]

_BACKLOG_LABELS = [
    "backlog",
    "remaining performance obligations",
    "contract backlog",
    "total backlog",
    "funded backlog",
]


def _pick(df: Optional[pd.DataFrame], labels: List[str]) -> Optional[float]:
    if df is None:
        return None
    for label in labels:
        val = _latest_value(df, label)
        if val is not None:
            return val
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_metrics(xbrl: Any) -> Dict[str, Optional[float]]:
    """
    Extract raw metric values from a single XBRL object.

    Returns a flat dict: metric_name → float (or None if not found).
    Values are in the native unit of the filing (usually USD thousands).
    """
    if xbrl is None:
        return {}

    stmts = getattr(xbrl, "statements", None)
    if stmts is None:
        return {}

    income_df: Optional[pd.DataFrame] = None
    cashflow_df: Optional[pd.DataFrame] = None
    balance_df: Optional[pd.DataFrame] = None

    try:
        income_df = _stmt_to_df(stmts.income_statement())
    except Exception:
        pass
    try:
        cashflow_df = _stmt_to_df(stmts.cash_flow_statement())
    except Exception:
        pass
    try:
        balance_df = _stmt_to_df(stmts.balance_sheet())
    except Exception:
        pass

    revenue = _pick(income_df, _REVENUE_LABELS)
    cogs = _pick(income_df, _COGS_LABELS)
    gross_profit = _pick(income_df, _GROSS_PROFIT_LABELS)

    # Derive gross margin % — prefer explicit gross profit, else compute
    gross_margin_pct: Optional[float] = None
    if gross_profit is not None and revenue and revenue != 0:
        gross_margin_pct = round(gross_profit / revenue * 100, 2)
    elif revenue and cogs and revenue != 0:
        gross_margin_pct = round((revenue - cogs) / revenue * 100, 2)

    net_income = _pick(income_df, ["Net Income", "Net Income Loss", "Profit or Loss"])
    operating_income = _pick(income_df, ["Operating Income"])

    sbc = _pick(cashflow_df, _SBC_LABELS)
    capex_raw = _pick(cashflow_df, _CAPEX_LABELS)
    # CapEx is usually negative in cash flow statement — store as positive
    capex = abs(capex_raw) if capex_raw is not None else None
    da = _pick(cashflow_df, _DA_LABELS)

    sbc_pct: Optional[float] = None
    if sbc is not None and revenue and revenue != 0:
        sbc_pct = round(sbc / revenue * 100, 2)

    shares = _pick(balance_df, _SHARES_LABELS)
    # Shares on balance sheet are often in actual units, not thousands — keep raw
    receivables = _pick(balance_df, _RECEIVABLES_LABELS)

    goodwill   = _pick(balance_df, _GOODWILL_LABELS)
    impairment = _pick(income_df, _IMPAIRMENT_LABELS)
    if impairment is not None and impairment < 0:
        impairment = abs(impairment)

    long_term_debt   = _pick(balance_df, _LONG_TERM_DEBT_LABELS)
    operating_cf     = _pick(cashflow_df, _OPERATING_CASHFLOW_LABELS)
    inventory        = _pick(balance_df, _INVENTORY_LABELS)
    # Backlog not in standard XBRL — best-effort fuzzy match
    backlog          = _pick(balance_df, _BACKLOG_LABELS)
    if backlog is None:
        backlog = _pick(income_df, _BACKLOG_LABELS)

    return {
        "Revenue": revenue,
        "Gross Margin %": gross_margin_pct,
        "Net Income": net_income,
        "Operating Income": operating_income,
        "Operating Cash Flow": operating_cf,
        "SBC": sbc,
        "SBC / Revenue %": sbc_pct,
        "CapEx": capex,
        "D&A": da,
        "Shares Outstanding": shares,
        "Receivables": receivables,
        "Inventory": inventory,
        "Long-Term Debt": long_term_debt,
        "Goodwill": goodwill,
        "Goodwill Impairment": impairment,
        "Backlog": backlog,
    }


def build_metrics_diff(
    current_metrics: Dict[str, Optional[float]],
    prior_metrics: Dict[str, Optional[float]],
) -> List[dict]:
    """
    Combine current + prior metric dicts into the metrics_diff list format
    required by the output contract and flags engine.
    """
    rows: List[dict] = []
    all_keys = list(current_metrics.keys())

    for key in all_keys:
        current_val = current_metrics.get(key)
        prior_val = prior_metrics.get(key)

        if current_val is None and prior_val is None:
            continue

        # Gross Margin % and SBC % are already percentages — label change_pct as pp (percentage points)
        if key.endswith("%"):
            change_pct = (
                round((current_val or 0) - (prior_val or 0), 2)
                if current_val is not None and prior_val is not None
                else None
            )
        else:
            change_pct = _pct_change(prior_val, current_val)

        rows.append({
            "metric": key,
            "prior": prior_val,
            "current": current_val,
            "change_pct": change_pct,
        })

    return rows
