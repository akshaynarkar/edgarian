from unittest.mock import MagicMock

import pandas as pd

from core.diff import diff_sections
from core.filing_cleaner import clean_text, extract_section
from core.flags import evaluate_flags
from core.metrics import _latest_value, _pct_change, build_metrics_diff, extract_metrics


def test_clean_text_normalizes_broken_item_headers():
    raw = "\nI T E M  1 A\nRisk Factors\n\nPage 2\n"
    cleaned = clean_text(raw)
    assert "ITEM 1A" in cleaned.upper()
    assert "Page 2" not in cleaned


def test_extract_section_basic_html():
    html = """
    <html><body>
    <div>Item 1. Business</div>
    <div>Overview paragraph.</div>
    <div>Item 1A. Risk Factors</div>
    <div>Risk paragraph one.</div>
    <div>Risk paragraph two.</div>
    <div>Item 1B. Unresolved Staff Comments</div>
    </body></html>
    """
    result = extract_section(html, "1A")
    assert "Risk paragraph one" in result
    assert "Item 1B" not in result


def test_diff_sections_reports_added_removed_modified():
    prior = "A\n\nB\n\nC"
    current = "A\n\nB changed\n\nD"
    diff = diff_sections(current, prior)
    assert diff["modified"]


def test_flags_new_risk_and_sbc_creep():
    # Paragraph must be >80 chars and not match artifact patterns to pass _is_real_paragraph
    long_risk_text = (
        "The Company has significant supply chain concentration in Vietnam and other "
        "Southeast Asian countries, which exposes it to geopolitical and operational risks."
    )
    metrics = [{"metric": "SBC / Revenue %", "prior": 2.99, "current": 3.09, "change_pct": 0.3}]
    section_diffs = {
        "risk_factors": {"added": [{"text": long_risk_text, "paragraph_index": 3}], "modified": []},
        "mda": {"modified": []},
        "revenue_rec": {"modified": []},
    }
    flags = evaluate_flags(metrics, section_diffs)
    types = {flag["type"] for flag in flags}
    assert "new_risk" in types
    assert "sbc_creep" in types
    # sbc_creep text should include the percentage values
    sbc_flag = next(f for f in flags if f["type"] == "sbc_creep")
    assert "2.99" in sbc_flag["text"] and "3.09" in sbc_flag["text"]


# ---------------------------------------------------------------------------
# metrics.py unit tests — all offline, no EDGAR network calls
# ---------------------------------------------------------------------------

def _make_mock_xbrl(income_data: dict, cashflow_data: dict, balance_data: dict):
    """Build a mock XBRL object whose statements return DataFrames."""

    def _make_stmt(data: dict):
        if not data:
            return None
        df = pd.DataFrame.from_dict(data, orient="index")
        # Columns simulate period dates (most recent first)
        df.columns = ["2024-09-30", "2023-09-30"][: len(df.columns)]
        stmt = MagicMock()
        stmt.to_dataframe.return_value = df
        return stmt

    stmts = MagicMock()
    stmts.income_statement.return_value = _make_stmt(income_data)
    stmts.cash_flow_statement.return_value = _make_stmt(cashflow_data)
    stmts.balance_sheet.return_value = _make_stmt(balance_data)

    xbrl = MagicMock()
    xbrl.statements = stmts
    return xbrl


def test_extract_metrics_revenue_and_gross_margin():
    xbrl = _make_mock_xbrl(
        income_data={
            "Revenue":       [391_035_000, 383_285_000],
            "Cost of Revenue": [210_352_000, 214_137_000],
            "Gross Profit":  [180_683_000, 169_148_000],
            "Net Income":    [93_736_000,  96_995_000],
        },
        cashflow_data={},
        balance_data={},
    )
    m = extract_metrics(xbrl)
    assert m["Revenue"] == 391_035_000
    assert m["Gross Margin %"] is not None
    assert 46.0 < m["Gross Margin %"] < 47.0  # ~46.2%


def test_extract_metrics_sbc_capex():
    xbrl = _make_mock_xbrl(
        income_data={"Revenue": [100_000, 90_000]},
        cashflow_data={
            "Stock-based compensation":        [11_688_000, 10_833_000],
            "Capital expenditures":            [-9_447_000, -10_708_000],
            "Depreciation and amortization":   [11_445_000, 11_519_000],
        },
        balance_data={},
    )
    m = extract_metrics(xbrl)
    assert m["SBC"] == 11_688_000
    assert m["CapEx"] == 9_447_000   # stored as positive
    assert m["D&A"] == 11_445_000


def test_extract_metrics_returns_empty_on_none_xbrl():
    assert extract_metrics(None) == {}


def test_build_metrics_diff_pct_change():
    current = {"Revenue": 391_035, "Gross Margin %": 46.2}
    prior   = {"Revenue": 383_285, "Gross Margin %": 44.1}
    rows = build_metrics_diff(current, prior)
    by_metric = {r["metric"]: r for r in rows}

    rev = by_metric["Revenue"]
    assert rev["prior"] == 383_285
    assert rev["current"] == 391_035
    assert abs(rev["change_pct"] - 2.02) < 0.1

    gm = by_metric["Gross Margin %"]
    # Percentage point diff, not % change
    assert abs(gm["change_pct"] - 2.1) < 0.01


def test_build_metrics_diff_skips_both_none():
    rows = build_metrics_diff({"Revenue": None}, {"Revenue": None})
    assert rows == []


def test_pct_change_edge_cases():
    assert _pct_change(0, 100) is None       # div by zero guard
    assert _pct_change(None, 100) is None
    assert _pct_change(100, None) is None
    assert _pct_change(100, 200) == 100.0


def test_latest_value_substring_match():
    df = pd.DataFrame({"2024": [100.0]}, index=["Total Net Revenue"])
    assert _latest_value(df, "Net Revenue") == 100.0


def test_latest_value_missing_returns_none():
    df = pd.DataFrame({"2024": [100.0]}, index=["Revenue"])
    assert _latest_value(df, "EBITDA") is None


# ---------------------------------------------------------------------------
# insider_cluster.py unit tests — all offline
# ---------------------------------------------------------------------------

from datetime import date
from unittest.mock import patch

import pandas as pd

from core.insider_cluster import detect_cluster_buys, classify_price_vs_52wk


def _make_tx(names, dates, tx_type="BUY") -> pd.DataFrame:
    return pd.DataFrame({
        "name":  names,
        "date":  pd.to_datetime(dates),
        "type":  [tx_type] * len(names),
        "shares": [1000] * len(names),
        "price":  [50.0] * len(names),
    })


def test_detect_cluster_buys_three_execs_within_30_days():
    tx = _make_tx(
        ["CEO", "CFO", "COO"],
        ["2024-01-01", "2024-01-10", "2024-01-25"],
    )
    flags = detect_cluster_buys(tx)
    # All three are within 30 days of the last buy — should cluster
    assert flags[-1] is True


def test_detect_cluster_buys_two_execs_no_cluster():
    tx = _make_tx(
        ["CEO", "CFO"],
        ["2024-01-01", "2024-01-10"],
    )
    flags = detect_cluster_buys(tx)
    assert all(f is False for f in flags)


def test_detect_cluster_buys_spread_beyond_30_days():
    tx = _make_tx(
        ["CEO", "CFO", "COO"],
        ["2024-01-01", "2024-01-20", "2024-03-01"],  # COO is 59 days after CEO
    )
    flags = detect_cluster_buys(tx)
    # COO's window (Mar 1 − 30 days = Feb 1) catches only COO herself
    assert flags[-1] is False


def test_classify_price_vs_52wk_near_low():
    mock_history = pd.DataFrame({
        "High": [120.0] * 252,
        "Low":  [80.0]  * 252,
    })
    with patch("core.insider_cluster.yf.Ticker") as mock_ticker:
        mock_ticker.return_value.history.return_value = mock_history
        result = classify_price_vs_52wk("AAPL", 82.0)
    assert result == "near_low"


def test_classify_price_vs_52wk_near_high():
    mock_history = pd.DataFrame({
        "High": [120.0] * 252,
        "Low":  [80.0]  * 252,
    })
    with patch("core.insider_cluster.yf.Ticker") as mock_ticker:
        mock_ticker.return_value.history.return_value = mock_history
        result = classify_price_vs_52wk("AAPL", 118.0)
    assert result == "near_high"


def test_classify_price_vs_52wk_mid():
    mock_history = pd.DataFrame({
        "High": [120.0] * 252,
        "Low":  [80.0]  * 252,
    })
    with patch("core.insider_cluster.yf.Ticker") as mock_ticker:
        mock_ticker.return_value.history.return_value = mock_history
        result = classify_price_vs_52wk("AAPL", 100.0)
    assert result == "mid"


def test_classify_price_vs_52wk_empty_history():
    with patch("core.insider_cluster.yf.Ticker") as mock_ticker:
        mock_ticker.return_value.history.return_value = pd.DataFrame()
        result = classify_price_vs_52wk("AAPL", 50.0)
    assert result == "mid"


# ---------------------------------------------------------------------------
# Net income collapse + goodwill impairment rules
# ---------------------------------------------------------------------------

def test_earnings_collapse_flag_no_goodwill():
    metrics = [
        {"metric": "Net Income", "prior": 950_000_000, "current": -81_000_000, "change_pct": -108.5},
    ]
    flags = evaluate_flags(metrics, {"risk_factors": {"added": [], "modified": []}, "mda": {"modified": []}, "revenue_rec": {"modified": []}})
    types = {f["type"] for f in flags}
    assert "earnings_collapse" in types


def test_goodwill_impairment_flag_when_goodwill_drops():
    metrics = [
        {"metric": "Net Income", "prior": 950_000_000, "current": -81_000_000, "change_pct": -108.5},
        {"metric": "Goodwill",   "prior": 1_500_000_000, "current": 800_000_000, "change_pct": -46.7},
    ]
    flags = evaluate_flags(metrics, {"risk_factors": {"added": [], "modified": []}, "mda": {"modified": []}, "revenue_rec": {"modified": []}})
    types = {f["type"] for f in flags}
    # Should fire goodwill_impairment, not plain earnings_collapse
    assert "goodwill_impairment" in types
    assert "earnings_collapse" not in types
    flag = next(f for f in flags if f["type"] == "goodwill_impairment")
    assert "impairment" in flag["text"].lower()
    assert flag["severity"] == "high"


def test_no_collapse_flag_for_small_decline():
    # 20% decline should NOT fire — below 25% threshold
    metrics = [
        {"metric": "Net Income", "prior": 1_000_000_000, "current": 800_000_000, "change_pct": -20.0},
    ]
    flags = evaluate_flags(metrics, {"risk_factors": {"added": [], "modified": []}, "mda": {"modified": []}, "revenue_rec": {"modified": []}})
    types = {f["type"] for f in flags}
    assert "earnings_collapse" not in types
    assert "goodwill_impairment" not in types


def test_no_collapse_flag_when_prior_was_loss():
    # If prior period was already a loss, % change is meaningless — should not fire
    metrics = [
        {"metric": "Net Income", "prior": -100_000_000, "current": -200_000_000, "change_pct": -100.0},
    ]
    flags = evaluate_flags(metrics, {"risk_factors": {"added": [], "modified": []}, "mda": {"modified": []}, "revenue_rec": {"modified": []}})
    types = {f["type"] for f in flags}
    assert "earnings_collapse" not in types


# ---------------------------------------------------------------------------
# New flag rules
# ---------------------------------------------------------------------------

def test_operating_loss_flag():
    metrics = [{"metric": "Operating Income", "prior": 500_000_000, "current": -50_000_000, "change_pct": -110.0}]
    flags = evaluate_flags(metrics, {"risk_factors": {"added": [], "modified": []}, "mda": {"modified": []}, "revenue_rec": {"modified": []}})
    assert any(f["type"] == "operating_loss" for f in flags)


def test_gross_margin_compression_flag():
    metrics = [{"metric": "Gross Margin %", "prior": 45.0, "current": 42.5, "change_pct": -2.5}]
    flags = evaluate_flags(metrics, {"risk_factors": {"added": [], "modified": []}, "mda": {"modified": []}, "revenue_rec": {"modified": []}})
    assert any(f["type"] == "gross_margin_compression" for f in flags)


def test_cash_conversion_flag():
    metrics = [
        {"metric": "Operating Cash Flow", "prior": 800_000_000, "current": 400_000_000, "change_pct": -50.0},
        {"metric": "Net Income",          "prior": 700_000_000, "current": 700_000_000, "change_pct": 0.0},
    ]
    flags = evaluate_flags(metrics, {"risk_factors": {"added": [], "modified": []}, "mda": {"modified": []}, "revenue_rec": {"modified": []}})
    assert any(f["type"] == "cash_conversion" for f in flags)


def test_debt_load_flag():
    metrics = [
        {"metric": "Long-Term Debt",    "prior": 3_000_000_000, "current": 4_000_000_000, "change_pct": 33.3},
        {"metric": "Operating Income",  "prior": 600_000_000,   "current": 600_000_000,   "change_pct": 0.0},
    ]
    flags = evaluate_flags(metrics, {"risk_factors": {"added": [], "modified": []}, "mda": {"modified": []}, "revenue_rec": {"modified": []}})
    assert any(f["type"] == "debt_load" for f in flags)


def test_inventory_build_flag():
    metrics = [
        {"metric": "Inventory", "prior": 500_000_000, "current": 700_000_000, "change_pct": 40.0},
        {"metric": "Revenue",   "prior": 5_000_000_000, "current": 5_100_000_000, "change_pct": 2.0},
    ]
    flags = evaluate_flags(metrics, {"risk_factors": {"added": [], "modified": []}, "mda": {"modified": []}, "revenue_rec": {"modified": []}})
    assert any(f["type"] == "inventory_build" for f in flags)


def test_book_to_bill_low_flag():
    metrics = [
        {"metric": "Backlog",  "prior": 8_000_000_000, "current": 7_000_000_000, "change_pct": -12.5},
        {"metric": "Revenue",  "prior": 9_000_000_000, "current": 9_000_000_000, "change_pct": 0.0},
    ]
    flags = evaluate_flags(metrics, {"risk_factors": {"added": [], "modified": []}, "mda": {"modified": []}, "revenue_rec": {"modified": []}})
    assert any(f["type"] == "book_to_bill_low" for f in flags)


def test_no_flag_for_healthy_financials():
    metrics = [
        {"metric": "Revenue",        "prior": 10e9, "current": 11e9,  "change_pct": 10.0},
        {"metric": "Net Income",     "prior": 1e9,  "current": 1.1e9, "change_pct": 10.0},
        {"metric": "Operating Income","prior": 1.5e9,"current": 1.6e9,"change_pct": 6.7},
        {"metric": "Gross Margin %", "prior": 45.0, "current": 45.5,  "change_pct": 0.5},
    ]
    flags = evaluate_flags(metrics, {"risk_factors": {"added": [], "modified": []}, "mda": {"modified": []}, "revenue_rec": {"modified": []}})
    bad_types = {"earnings_collapse","goodwill_impairment","operating_loss","gross_margin_compression","debt_load"}
    assert not any(f["type"] in bad_types for f in flags)
