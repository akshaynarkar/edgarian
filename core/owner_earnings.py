"""Owner earnings calculation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional


@dataclass
class OwnerEarningsResult:
    value: Optional[float]
    yoy_change_pct: Optional[float]
    components: Dict[str, Optional[float]]


LABEL_MAP = {
    "net_income": ["Net Income", "NetIncomeLoss"],
    "da": ["Depreciation", "DepreciationAndAmortization", "DepreciationDepletionAndAmortization"],
    "capex": ["Capital Expenditures", "PaymentsToAcquirePropertyPlantAndEquipment"],
    "working_capital_change": [
        "Change in Working Capital",
        "IncreaseDecreaseInOperatingAssetsLiabilitiesNetOfAcquiredBusinesses",
    ],
}


def _get_statement_rows(statement: Any) -> Dict[str, float]:
    """Convert a Statement to a label→latest-value dict. Delegates to metrics._stmt_to_df."""
    from core.metrics import _stmt_to_df, _first_numeric
    rows: Dict[str, float] = {}
    df = _stmt_to_df(statement)
    if df is None:
        return rows
    for idx in df.index:
        val = _first_numeric(df.loc[idx])
        if val is not None:
            rows[str(idx)] = val
    return rows


def _pick_value(rows: Dict[str, float], labels: Iterable[str]) -> Optional[float]:
    lowered = {k.lower(): v for k, v in rows.items()}
    for label in labels:
        if label.lower() in lowered:
            return lowered[label.lower()]
    for key, value in lowered.items():
        if any(label.lower() in key for label in labels):
            return value
    return None


def compute_owner_earnings(current_cashflow: Any, prior_cashflow: Any = None) -> OwnerEarningsResult:
    current_rows = _get_statement_rows(current_cashflow)
    prior_rows = _get_statement_rows(prior_cashflow)

    current_components = {name: _pick_value(current_rows, labels) for name, labels in LABEL_MAP.items()}
    prior_components = {name: _pick_value(prior_rows, labels) for name, labels in LABEL_MAP.items()}

    def calc(parts: Dict[str, Optional[float]]) -> Optional[float]:
        if parts["net_income"] is None or parts["da"] is None or parts["capex"] is None or parts["working_capital_change"] is None:
            return None
        return parts["net_income"] + parts["da"] - parts["capex"] - parts["working_capital_change"]

    current_value = calc(current_components)
    prior_value = calc(prior_components)
    yoy_change_pct = None
    if current_value is not None and prior_value not in (None, 0):
        yoy_change_pct = ((current_value - prior_value) / abs(prior_value)) * 100.0

    return OwnerEarningsResult(value=current_value, yoy_change_pct=yoy_change_pct, components=current_components)
