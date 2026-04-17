"""Deterministic rule engine for Edgarian red flags."""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional

SEVERITY_COLOR = {
    "high":   "red",
    "medium": "amber",
    "info":   "blue",
}

LANGUAGE_SHIFT_FROM = {"may", "could", "might"}
LANGUAGE_SHIFT_TO   = {"will", "expects", "anticipates"}

_MIN_PARAGRAPH_LEN = 80

_ARTIFACT_RE = re.compile(
    r"""
    ^\s*(
        \d+\s*$                             |
        .{0,60}\|\s*\d{4}\s*(form\s*)?\d+  |
        table\s+of\s+contents               |
        part\s+[ivx]+\b                     |
        item\s+\d+[a-c]?\b\s*$             |
        f[-\s]?\d+\s*$                      |
        back\s+to\s+top                     |
        index\s+to\s+financial
    )\s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _is_real_paragraph(text: str) -> bool:
    if not text or len(text.strip()) < _MIN_PARAGRAPH_LEN:
        return False
    return not _ARTIFACT_RE.match(text.strip())


def _metric_map(metrics_diff: Iterable[dict]) -> Dict[str, dict]:
    return {row.get("metric", ""): row for row in metrics_diff}


def _make_flag(flag_type: str, severity: str, text: str, source: str) -> dict:
    return {
        "type":     flag_type,
        "severity": severity,
        "color":    SEVERITY_COLOR[severity],
        "text":     text,
        "source":   source,
    }


def _fmt(val: Optional[float], prefix: str = "$") -> str:
    """Format a dollar value with B/M suffix."""
    if val is None:
        return "N/A"
    if abs(val) >= 1e9:
        return f"{prefix}{val/1e9:.1f}B"
    if abs(val) >= 1e6:
        return f"{prefix}{val/1e6:.0f}M"
    return f"{prefix}{val:,.0f}"


def _find_new_risk_paragraphs(section_diffs: Dict[str, dict]) -> List[dict]:
    rf = section_diffs.get("risk_factors", {})
    results = []
    for item in rf.get("added", []):
        text = item.get("text", "")
        if _is_real_paragraph(text):
            results.append({"text": text, "source": f"Item 1A, paragraph {item.get('paragraph_index', '?')}"})
    for item in rf.get("modified", []):
        prior   = item.get("prior_text") or ""
        current = item.get("current_text") or ""
        if _is_real_paragraph(current) and len(current) > len(prior) + 40:
            idx = item.get("current_paragraph_index", "?")
            results.append({"text": current, "source": f"Item 1A, paragraph {idx} (expanded)"})
    return results


def evaluate_flags(metrics_diff: List[dict], section_diffs: Dict[str, dict]) -> List[dict]:
    flags: List[dict] = []
    metrics = _metric_map(metrics_diff)

    # ------------------------------------------------------------------ #
    # TEXT RULES
    # ------------------------------------------------------------------ #

    new_risks = _find_new_risk_paragraphs(section_diffs)
    for risk in new_risks[:3]:
        snippet = risk["text"][:200].rstrip() + ("…" if len(risk["text"]) > 200 else "")
        flags.append(_make_flag("new_risk", "high", f"New/expanded risk: {snippet}", risk["source"]))

    mda_modified = section_diffs.get("mda", {}).get("modified", [])
    for change in mda_modified:
        before = (change.get("prior_text") or "").lower()
        after  = (change.get("current_text") or "").lower()
        if not _is_real_paragraph(after):
            continue
        if any(t in before for t in LANGUAGE_SHIFT_FROM) and any(t in after for t in LANGUAGE_SHIFT_TO):
            from_words = [t for t in LANGUAGE_SHIFT_FROM if t in before]
            to_words   = [t for t in LANGUAGE_SHIFT_TO   if t in after]
            flags.append(_make_flag(
                "language_shift", "medium",
                f"Language shift in MD&A: '{from_words[0]}' → '{to_words[0]}'",
                "Item 7"
            ))
            break

    rev_rec_modified = section_diffs.get("revenue_rec", {}).get("modified", [])
    substantive = [c for c in rev_rec_modified if _is_real_paragraph(c.get("current_text", ""))]
    if substantive:
        flags.append(_make_flag("rev_rec_change", "medium",
                                "Revenue recognition wording changed",
                                "Item 8 / Revenue recognition note"))

    # ------------------------------------------------------------------ #
    # FINANCIAL RULES
    # ------------------------------------------------------------------ #

    revenue     = metrics.get("Revenue")
    net_income  = metrics.get("Net Income")
    op_income   = metrics.get("Operating Income")
    op_cf       = metrics.get("Operating Cash Flow")
    gross_margin = metrics.get("Gross Margin %")
    sbc         = metrics.get("SBC / Revenue %")
    shares      = metrics.get("Shares Outstanding")
    recv        = metrics.get("Receivables")
    capex       = metrics.get("CapEx")
    inventory   = metrics.get("Inventory")
    ltd         = metrics.get("Long-Term Debt")
    goodwill    = metrics.get("Goodwill")
    backlog     = metrics.get("Backlog")

    # — Net income collapse / goodwill impairment —
    if net_income:
        ni_chg     = net_income.get("change_pct") or 0
        prior_ni   = net_income.get("prior")
        current_ni = net_income.get("current")
        if ni_chg < -25 and prior_ni and prior_ni > 0:
            gw_dropped = goodwill is not None and (goodwill.get("change_pct") or 0) < -10
            if gw_dropped:
                gw_chg = goodwill.get("change_pct", 0)
                flags.append(_make_flag(
                    "goodwill_impairment", "high",
                    f"Net income collapsed {abs(ni_chg):.0f}% "
                    f"({_fmt(prior_ni)} → {_fmt(current_ni)}) "
                    f"alongside goodwill decline of {abs(gw_chg):.0f}% — "
                    "likely acquisition impairment write-down",
                    "Income Statement + Balance Sheet (Goodwill)"
                ))
            else:
                flags.append(_make_flag(
                    "earnings_collapse", "high",
                    f"Net income declined {abs(ni_chg):.0f}% YoY "
                    f"({_fmt(prior_ni)} → {_fmt(current_ni)})",
                    "Income Statement"
                ))

    # — Operating loss (core business losing money, independent of impairments) —
    if op_income:
        prior_op   = op_income.get("prior")
        current_op = op_income.get("current")
        op_chg     = op_income.get("change_pct") or 0
        if current_op is not None and current_op < 0:
            flags.append(_make_flag(
                "operating_loss", "high",
                f"Operating income is negative ({_fmt(current_op)}) — "
                "core business is loss-making",
                "Income Statement"
            ))
        elif op_chg < -30 and prior_op and prior_op > 0:
            flags.append(_make_flag(
                "operating_deterioration", "medium",
                f"Operating income declined {abs(op_chg):.0f}% YoY "
                f"({_fmt(prior_op)} → {_fmt(current_op)})",
                "Income Statement"
            ))

    # — Gross margin compression —
    if gross_margin:
        gm_chg = gross_margin.get("change_pct") or 0
        prior_gm   = gross_margin.get("prior")
        current_gm = gross_margin.get("current")
        if gm_chg < -2 and prior_gm is not None and current_gm is not None:
            flags.append(_make_flag(
                "gross_margin_compression", "medium",
                f"Gross margin compressed {abs(gm_chg):.1f}pp YoY "
                f"({prior_gm:.1f}% → {current_gm:.1f}%)",
                "Income Statement"
            ))

    # — Cash conversion (operating CF vs net income divergence) —
    if op_cf and net_income:
        cf_val = op_cf.get("current")
        ni_val = net_income.get("current")
        if cf_val is not None and ni_val and ni_val > 0:
            ratio = cf_val / ni_val
            if ratio < 0.7:
                flags.append(_make_flag(
                    "cash_conversion", "medium",
                    f"Operating cash flow ({_fmt(cf_val)}) is only "
                    f"{ratio*100:.0f}% of net income ({_fmt(ni_val)}) — "
                    "earnings quality concern, check accruals",
                    "Cash Flow vs Income Statement"
                ))

    # — Debt load —
    if ltd and op_income:
        debt_val = ltd.get("current")
        op_val   = op_income.get("current")
        debt_chg = ltd.get("change_pct") or 0
        if debt_val and op_val and op_val > 0:
            debt_to_op = debt_val / op_val
            if debt_to_op > 5 and debt_chg > 10:
                flags.append(_make_flag(
                    "debt_load", "medium",
                    f"Long-term debt ({_fmt(debt_val)}) is "
                    f"{debt_to_op:.1f}x operating income and grew {debt_chg:.0f}% YoY",
                    "Balance Sheet + Income Statement"
                ))

    # — SBC creep —
    if sbc and (sbc.get("change_pct") or 0) > 0.2:
        prior_pct   = sbc.get("prior")
        current_pct = sbc.get("current")
        detail = (f"({prior_pct:.2f}% → {current_pct:.2f}%)"
                  if isinstance(prior_pct, (int, float)) and isinstance(current_pct, (int, float))
                  else "")
        flags.append(_make_flag(
            "sbc_creep", "medium",
            f"SBC as % of revenue up {sbc['change_pct']:.2f}pp YoY {detail}".strip(),
            "Cash Flow Statement"
        ))

    # — Dilution —
    if shares and (shares.get("change_pct") or 0) > 1.0:
        flags.append(_make_flag(
            "dilution", "medium",
            f"Shares outstanding increased {shares['change_pct']:.2f}% YoY",
            "Balance Sheet / Equity"
        ))

    # — Receivables outpacing revenue —
    if recv and revenue:
        recv_chg = recv.get("change_pct") or 0
        rev_chg  = revenue.get("change_pct") or 0
        if recv_chg > rev_chg + 5:
            flags.append(_make_flag(
                "recv_growth", "medium",
                f"Receivables growing {recv_chg:.1f}% vs revenue {rev_chg:.1f}% — "
                "potential channel stuffing or collections risk",
                "Balance Sheet vs Income Statement"
            ))

    # — Inventory build —
    if inventory and revenue:
        inv_chg = inventory.get("change_pct") or 0
        rev_chg = revenue.get("change_pct") or 0
        if inv_chg > rev_chg + 10:
            flags.append(_make_flag(
                "inventory_build", "medium",
                f"Inventory growing {inv_chg:.1f}% vs revenue {rev_chg:.1f}% — "
                "potential demand softness or overstocking",
                "Balance Sheet vs Income Statement"
            ))

    # — CapEx declining while revenue growing —
    if capex and revenue:
        capex_chg = capex.get("change_pct") or 0
        rev_chg   = revenue.get("change_pct") or 0
        if capex_chg < 0 and rev_chg > 0:
            flags.append(_make_flag(
                "capex_decline", "info",
                f"CapEx declining {abs(capex_chg):.1f}% while revenue growing {rev_chg:.1f}%",
                "Cash Flow Statement"
            ))

    # — Book-to-bill (backlog / revenue) — defense/industrial tickers —
    if backlog and revenue:
        backlog_val = backlog.get("current")
        revenue_val = revenue.get("current")
        backlog_chg = backlog.get("change_pct") or 0
        if backlog_val and revenue_val and revenue_val > 0:
            btb = backlog_val / revenue_val
            if btb < 1.0:
                flags.append(_make_flag(
                    "book_to_bill_low", "medium",
                    f"Backlog ({_fmt(backlog_val)}) is {btb:.2f}x trailing revenue — "
                    "sub-1.0 book-to-bill signals contracting demand",
                    "Balance Sheet / Backlog disclosure"
                ))
            elif btb > 1.5 and backlog_chg > 10:
                flags.append(_make_flag(
                    "book_to_bill_strong", "info",
                    f"Strong backlog ({_fmt(backlog_val)}, {btb:.2f}x revenue, "
                    f"+{backlog_chg:.0f}% YoY) — future revenue visibility high",
                    "Balance Sheet / Backlog disclosure"
                ))

    return flags
