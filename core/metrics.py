"""
Extract key financial metrics from edgartools XBRL statements.
Produces the metrics_diff rows consumed by flags.py and the output contract.

Strategy: prefer StandardConcept labels (cross-company stable), fall back to
fuzzy label matching for metrics not yet in the StandardConcept enum.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
import pandas as pd


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _stmt_to_df(stmt: Any) -> Optional[pd.DataFrame]:
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
    if "label" in df.columns:
        df = df.set_index("label")
    df = df[~df.index.duplicated(keep="first")]
    _META_COLS = {
        "concept", "standard_concept", "balance", "weight", "preferred_sign",
        "level", "abstract", "dimension", "is_breakdown", "dimension_axis",
        "dimension_member", "dimension_member_label", "dimension_label",
        "parent_concept", "parent_abstract_concept",
    }
    cols = [c for c in df.columns if c not in _META_COLS]
    df = df[cols]
    numeric_cols = [
        c for c in df.columns
        if pd.to_numeric(df[c], errors="coerce").notna().any()
    ]
    if not numeric_cols:
        return None
    return df[numeric_cols]


def _latest_value(df: pd.DataFrame, label: str) -> Optional[float]:
    label_lower = label.lower()
    for idx in df.index:
        if str(idx).lower() == label_lower:
            return _first_numeric(df.loc[idx])
    for idx in df.index:
        if label_lower in str(idx).lower():
            return _first_numeric(df.loc[idx])
    return None


def _first_numeric(row: pd.Series) -> Optional[float]:
    coerced = pd.to_numeric(row, errors="coerce")
    for val in coerced:
        if val is not None and not pd.isna(val):
            return float(val)
    return None


def _pct_change(prior: Optional[float], current: Optional[float]) -> Optional[float]:
    if prior is None or current is None or prior == 0:
        return None
    return round((current - prior) / abs(prior) * 100, 2)


def _metric_row(metric, prior, current, unit="USD_thousands"):
    return {
        "metric": metric, "prior": prior, "current": current,
        "change_pct": _pct_change(prior, current), "unit": unit,
    }


# ---------------------------------------------------------------------------
# Label lists — exact/common first, then fallbacks
# Covers: AAPL, CROX, RTX, NVDA, MSFT (and most other large-caps)
# ---------------------------------------------------------------------------

_REVENUE_LABELS = [
    "Revenue", "Revenues", "Net Revenue", "Net Revenues",
    "Net Sales", "Net sales", "Total Revenue", "Total Revenues",
    "Contract Revenue", "Product Revenue",
]

_COGS_LABELS = [
    "Cost of sales",                            # AAPL, RTX
    "Cost of revenue",                          # NVDA, MSFT
    "Cost of Sales",
    "Cost of Revenue",
    "Cost of Goods Sold",
    "Cost of Goods and Services Sold",
    "Costs and Expenses",
]

_GROSS_PROFIT_LABELS = [
    "Gross profit",                             # CROX, NVDA
    "Gross margin",                             # MSFT, AAPL
    "Gross Profit",
    "Gross Margin",
]

_OPERATING_INCOME_LABELS = [
    "Operating income",                         # NVDA, MSFT
    "Operating Income",                         # standard
    "Income from operations",                   # CROX exact
    "Operating profit (loss)",                  # RTX exact
    "Operating profit",
    "Operating loss",
]

_SBC_LABELS = [
    "Share-based compensation expense",         # AAPL exact
    "Stock-based compensation expense",         # NVDA, MSFT exact
    "Share-based compensation",                 # CROX exact
    "Stock compensation cost",                  # RTX exact
    "Stock-based compensation",
    "Equity-based compensation",
    "stock compensation expense",
]

_CAPEX_LABELS = [
    "Payments for acquisition of property, plant and equipment",  # AAPL exact
    "Purchases related to property and equipment and intangible assets",  # NVDA exact
    "Additions to property and equipment",      # MSFT exact
    "Capital expenditures",                     # RTX exact
    "Purchases of property, equipment, and software",  # CROX exact
    "purchases of property",
    "acquisition of property",
    "payments to acquire property",
    "capital spending",
]

_DA_LABELS = [
    "Depreciation and amortization",            # AAPL, CROX, RTX exact
    "Depreciation, amortization, and other",    # MSFT exact
    "depreciation and amortization",
    "Depreciation, amortization",
    "depreciation & amortization",
]

_SHARES_LABELS = [
    "Common stock, shares outstanding (in shares)",   # AAPL exact — cell value is real share count
    "common shares outstanding",
    # NOTE: most other companies embed share counts in the label text itself
    # and store 0 or par value as the cell value — handled by _pick_shares() below
]

# Weighted average shares from income statement — reliable fallback for all tickers
_WEIGHTED_AVG_SHARE_LABELS = [
    "Diluted (in shares)",                      # AAPL, CROX, RTX exact
    "diluted (in shares)",
    "Diluted shares (in shares)",
    "Diluted shares",
    "diluted shares",
    "weighted average shares",
    "weighted-average shares",
    "shares used in computing earnings per share",
]

_RECEIVABLES_LABELS = [
    "Accounts receivable, net",                 # RTX, NVDA, MSFT exact
    "Accounts receivable, net of allowances",   # CROX exact (substring match)
    "accounts receivable",
    "trade receivables",
    "net receivables",
]

_GOODWILL_LABELS = [
    "Goodwill",
    "goodwill, net",
]

_IMPAIRMENT_LABELS = [
    "Goodwill impairment",                      # CROX exact
    "goodwill impairment",
    "impairment of goodwill",
    "goodwill and intangible asset impairment",
    "asset impairment",
]

_LONG_TERM_DEBT_LABELS = [
    "Long-term debt",                           # RTX, NVDA, MSFT exact
    "Long-term borrowings",                     # CROX exact
    "term debt",                                # AAPL (substring catches "Term debt")
    "long term debt",
    "long-term debt, net",
    "notes payable",
]

_OPERATING_CASHFLOW_LABELS = [
    "Cash generated by operating activities",   # AAPL exact
    "Cash provided by operating activities",    # CROX exact
    "Net cash flows provided by operating activities",  # RTX exact
    "Net cash provided by operating activities",        # NVDA exact
    "Net cash from operations",                 # MSFT exact
    "net cash generated by operating activities",
    "cash flows from operating activities",
    "operating activities",
]

_INVENTORY_LABELS = [
    "Inventories",
    "Inventory, net",                           # RTX
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


def _pick_shares(
    balance_df: Optional[pd.DataFrame],
    income_df:  Optional[pd.DataFrame],
) -> Optional[float]:
    """
    Shares outstanding — many companies embed the count in the BS label text
    itself (e.g. '...24,304 shares issued and outstanding') and store 0 or
    par value as the numeric cell, making substring match unreliable.

    Strategy:
    1. Try balance sheet with safe labels where the cell value IS the count (AAPL)
    2. Fall back to weighted average diluted shares from income statement —
       always stored as a real number across all tickers
    """
    # Step 1 — balance sheet (AAPL-style, cell value = share count)
    val = _pick(balance_df, _SHARES_LABELS)
    if val is not None and val > 1_000:   # guard: par value is 0 or 1
        return val

    # Step 2 — weighted average diluted from income statement
    val = _pick(income_df, _WEIGHTED_AVG_SHARE_LABELS)
    if val is not None and val > 1_000:
        return val

    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_metrics(xbrl: Any) -> Dict[str, Optional[float]]:
    if xbrl is None:
        return {}
    stmts = getattr(xbrl, "statements", None)
    if stmts is None:
        return {}

    income_df:   Optional[pd.DataFrame] = None
    cashflow_df: Optional[pd.DataFrame] = None
    balance_df:  Optional[pd.DataFrame] = None

    try:
        income_df   = _stmt_to_df(stmts.income_statement())
    except Exception:
        pass
    try:
        cashflow_df = _stmt_to_df(stmts.cash_flow_statement())
    except Exception:
        pass
    try:
        balance_df  = _stmt_to_df(stmts.balance_sheet())
    except Exception:
        pass

    revenue      = _pick(income_df, _REVENUE_LABELS)
    cogs         = _pick(income_df, _COGS_LABELS)
    gross_profit = _pick(income_df, _GROSS_PROFIT_LABELS)

    gross_margin_pct: Optional[float] = None
    if gross_profit is not None and revenue and revenue != 0:
        gross_margin_pct = round(gross_profit / revenue * 100, 2)
    elif revenue and cogs and revenue != 0:
        gross_margin_pct = round((revenue - cogs) / revenue * 100, 2)

    net_income       = _pick(income_df, ["Net income", "Net income (loss)", "Net Income", "Net Income Loss", "Profit or Loss"])
    operating_income = _pick(income_df, _OPERATING_INCOME_LABELS)
    sbc              = _pick(cashflow_df, _SBC_LABELS)
    capex_raw        = _pick(cashflow_df, _CAPEX_LABELS)
    capex            = abs(capex_raw) if capex_raw is not None else None
    da               = _pick(cashflow_df, _DA_LABELS)

    sbc_pct: Optional[float] = None
    if sbc is not None and revenue and revenue != 0:
        sbc_pct = round(sbc / revenue * 100, 2)

    shares         = _pick_shares(balance_df, income_df)
    receivables    = _pick(balance_df, _RECEIVABLES_LABELS)
    goodwill       = _pick(balance_df, _GOODWILL_LABELS)
    impairment     = _pick(income_df, _IMPAIRMENT_LABELS)
    if impairment is not None and impairment < 0:
        impairment = abs(impairment)
    long_term_debt = _pick(balance_df, _LONG_TERM_DEBT_LABELS)
    operating_cf   = _pick(cashflow_df, _OPERATING_CASHFLOW_LABELS)
    inventory      = _pick(balance_df, _INVENTORY_LABELS)
    backlog        = _pick(balance_df, _BACKLOG_LABELS) or _pick(income_df, _BACKLOG_LABELS)

    return {
        "Revenue":             revenue,
        "Gross Margin %":      gross_margin_pct,
        "Net Income":          net_income,
        "Operating Income":    operating_income,
        "Operating Cash Flow": operating_cf,
        "SBC":                 sbc,
        "SBC / Revenue %":     sbc_pct,
        "CapEx":               capex,
        "D&A":                 da,
        "Shares Outstanding":  shares,
        "Receivables":         receivables,
        "Inventory":           inventory,
        "Long-Term Debt":      long_term_debt,
        "Goodwill":            goodwill,
        "Goodwill Impairment": impairment,
        "Backlog":             backlog,
    }


def build_metrics_diff(
    current_metrics: Dict[str, Optional[float]],
    prior_metrics:   Dict[str, Optional[float]],
) -> List[dict]:
    rows: List[dict] = []
    for key in current_metrics:
        current_val = current_metrics.get(key)
        prior_val   = prior_metrics.get(key)
        if current_val is None and prior_val is None:
            continue
        if key.endswith("%"):
            change_pct = (
                round((current_val or 0) - (prior_val or 0), 2)
                if current_val is not None and prior_val is not None else None
            )
        else:
            change_pct = _pct_change(prior_val, current_val)
        rows.append({
            "metric": key, "prior": prior_val,
            "current": current_val, "change_pct": change_pct,
        })
    return rows
