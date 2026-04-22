"""
valuation.py
============
Financial input validation and interactive resolution layer for valuation pipelines.

Design principles
-----------------
1. Accuracy       – every value is range-checked, type-safe, and cross-validated
                    against related fields before it reaches downstream logic.
2. Completeness   – all nine financial fields are covered; missing or partial
                    data is detected and resolved before proceeding.
3. Consistency    – a single, uniform validation pipeline handles every field;
                    no ad-hoc special-casing.
4. Rules          – hard financial domain rules (market_cap > 0, revenue ≥ 0,
                    net_income ≤ revenue, FCF ≤ operating_cash_flow + tolerance,
                    cash ≤ market_cap, etc.) are enforced as first-class checks.
5. Timeliness     – data staleness is detected when `data_as_of` is supplied;
                    stale data triggers a warning or blocks execution depending
                    on configuration.
6. Interactive    – when values are null, invalid, or suspicious the resolver
                    pauses and asks the user for a corrected value via stdin
                    (or an injectable prompt callable for testing / GUI use).
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from math import isfinite
from typing import Any, Callable, Dict, List, Optional, Tuple

from utils.financials import (
    CASH_KEYS,
    EQUITY_KEYS,
    NET_INCOME_KEYS,
    OPERATING_CASH_FLOW_KEYS,
    REVENUE_KEYS,
    balance_value,
    cashflow_value,
    current_free_cash_flow,
    income_value,
    is_missing,
    market_cap_value,
    normalize_output,
    normalized_free_cash_flow,
    safe_div,
    total_debt_value,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Severity constants
# ---------------------------------------------------------------------------

SEVERITY_CRITICAL = "CRITICAL"   # Must be resolved – blocks all valuation.
SEVERITY_WARNING  = "WARNING"    # Suspicious but non-blocking; user prompted.
SEVERITY_INFO     = "INFO"       # Informational only; no prompt required.

# ---------------------------------------------------------------------------
# Timeliness configuration
# ---------------------------------------------------------------------------

# Data older than this is considered stale and will surface a warning.
STALE_DATA_WARNING_DAYS: int = 90
# Data older than this blocks the pipeline entirely.
STALE_DATA_BLOCK_DAYS: int = 365

# ---------------------------------------------------------------------------
# Cross-field consistency rules
# ---------------------------------------------------------------------------

# Maximum ratio by which |net_income| may exceed revenue.
# A net loss can be large, but a profit > revenue is almost always a data error.
MAX_NET_INCOME_TO_REVENUE_RATIO: float = 1.0

# FCF should not exceed operating cash flow by more than this factor.
# (capex cannot be negative in most datasets)
MAX_FCF_OCF_EXCESS_FACTOR: float = 1.05

# Cash should not exceed market cap (extremely unusual; likely data error).
MAX_CASH_TO_MARKET_CAP_RATIO: float = 2.0

# ---------------------------------------------------------------------------
# Issue dataclass
# ---------------------------------------------------------------------------

@dataclass
class ValidationIssue:
    """Represents a single validation finding for one financial field."""
    field: str
    severity: str                   # CRITICAL | WARNING | INFO
    reason: str
    current_value: Optional[float]
    expected_source: str
    # Whether the pipeline must block until this is resolved.
    blocks_pipeline: bool = False
    # Whether the user has already supplied a corrected value.
    resolved: bool = False
    # The final accepted value after resolution.
    resolved_value: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field":          self.field,
            "severity":       self.severity,
            "reason":         self.reason,
            "current_value":  self.current_value,
            "expected_source": self.expected_source,
            "blocks_pipeline": self.blocks_pipeline,
            "resolved":       self.resolved,
            "resolved_value": self.resolved_value,
        }


# ---------------------------------------------------------------------------
# Numeric helpers
# ---------------------------------------------------------------------------

def _to_number(value: Any) -> Optional[float]:
    """
    Convert *value* to a clean float.
    Returns None for: None, complex, non-numeric strings, NaN, ±Inf.
    """
    if is_missing(value) or value is None or isinstance(value, complex):
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    return num if isfinite(num) else None


def _positive_number(value: Any) -> Optional[float]:
    """
    Return *value* only if it converts to a strictly positive finite float.
    Used for ratio denominators where zero/negative values are meaningless.
    """
    num = _to_number(value)
    return num if (num is not None and num > 0) else None


# ---------------------------------------------------------------------------
# Field fetchers  (unchanged interface, same as original)
# ---------------------------------------------------------------------------

def _fetch_market_cap(data: Dict[str, Any]) -> Any:
    info = data.get("info", {}) if isinstance(data.get("info"), dict) else {}
    return market_cap_value(info)

def _fetch_net_income(data: Dict[str, Any]) -> Any:
    return income_value(data, NET_INCOME_KEYS)

def _fetch_revenue(data: Dict[str, Any]) -> Any:
    return income_value(data, REVENUE_KEYS)

def _fetch_equity(data: Dict[str, Any]) -> Any:
    return balance_value(data, EQUITY_KEYS)

def _fetch_cash(data: Dict[str, Any]) -> Any:
    return balance_value(data, CASH_KEYS)

def _fetch_total_debt(data: Dict[str, Any]) -> Any:
    return total_debt_value(data)

def _fetch_operating_cash_flow(data: Dict[str, Any]) -> Any:
    return cashflow_value(data, OPERATING_CASH_FLOW_KEYS)

def _fetch_current_fcf(data: Dict[str, Any]) -> Any:
    return current_free_cash_flow(data)

def _fetch_normalized_fcf(data: Dict[str, Any]) -> Any:
    return normalized_free_cash_flow(data)


# ---------------------------------------------------------------------------
# Field registry
# ---------------------------------------------------------------------------

REQUIRED_FIELDS: Dict[str, Dict[str, Any]] = {
    "market_cap": {
        "fetcher":   _fetch_market_cap,
        "source":    "info / market_cap_value(info)",
        "critical":  True,
        "unit":      "currency",
        # A negative or zero market cap is impossible for a listed entity.
        "min_value": 1.0,
        "max_value": None,
        "allow_negative": False,
        "description": "Total market capitalisation (shares × price).",
    },
    "net_income": {
        "fetcher":   _fetch_net_income,
        "source":    "income_value(data, NET_INCOME_KEYS)",
        "critical":  True,
        "unit":      "currency",
        "min_value": None,        # Losses are valid.
        "max_value": None,
        "allow_negative": True,
        "description": "Net income (profit after tax); negative = net loss.",
    },
    "revenue": {
        "fetcher":   _fetch_revenue,
        "source":    "income_value(data, REVENUE_KEYS)",
        "critical":  True,
        "unit":      "currency",
        "min_value": 0.0,         # Revenue of exactly zero is suspicious.
        "max_value": None,
        "allow_negative": False,
        "description": "Total revenue / turnover for the period.",
    },
    "equity": {
        "fetcher":   _fetch_equity,
        "source":    "balance_value(data, EQUITY_KEYS)",
        "critical":  True,
        "unit":      "currency",
        "min_value": None,        # Negative equity (liabilities > assets) is valid.
        "max_value": None,
        "allow_negative": True,
        "description": "Shareholders' equity (book value of net assets).",
    },
    "cash": {
        "fetcher":   _fetch_cash,
        "source":    "balance_value(data, CASH_KEYS)",
        "critical":  False,
        "unit":      "currency",
        "min_value": 0.0,
        "max_value": None,
        "allow_negative": False,
        "description": "Cash and cash equivalents on the balance sheet.",
    },
    "total_debt": {
        "fetcher":   _fetch_total_debt,
        "source":    "total_debt_value(data)",
        "critical":  False,
        "unit":      "currency",
        "min_value": 0.0,
        "max_value": None,
        "allow_negative": False,
        "description": "Total financial debt (short-term + long-term).",
    },
    "operating_cash_flow": {
        "fetcher":   _fetch_operating_cash_flow,
        "source":    "cashflow_value(data, OPERATING_CASH_FLOW_KEYS)",
        "critical":  False,
        "unit":      "currency",
        "min_value": None,
        "max_value": None,
        "allow_negative": True,
        "description": "Cash generated from operating activities.",
    },
    "current_fcf": {
        "fetcher":   _fetch_current_fcf,
        "source":    "current_free_cash_flow(data)",
        "critical":  False,
        "unit":      "currency",
        "min_value": None,
        "max_value": None,
        "allow_negative": True,
        "description": "Free cash flow for the most recent period.",
    },
    "normalized_fcf": {
        "fetcher":   _fetch_normalized_fcf,
        "source":    "normalized_free_cash_flow(data)",
        "critical":  False,
        "unit":      "currency",
        "min_value": None,
        "max_value": None,
        "allow_negative": True,
        "description": "Normalised / smoothed free cash flow.",
    },
}


# ---------------------------------------------------------------------------
# Per-field accuracy checks
# ---------------------------------------------------------------------------

def _field_issues(
    field: str,
    value: Optional[float],
    meta: Dict[str, Any],
) -> List[ValidationIssue]:
    """
    Run all per-field accuracy rules for *field* = *value*.
    Returns a (possibly empty) list of ValidationIssue objects.
    """
    issues: List[ValidationIssue] = []
    src = meta["source"]
    is_critical = meta["critical"]

    # ── NULL / non-numeric ──────────────────────────────────────────────────
    if value is None:
        issues.append(ValidationIssue(
            field=field,
            severity=SEVERITY_CRITICAL if is_critical else SEVERITY_WARNING,
            reason="Value is NULL, non-numeric, NaN, or infinite.",
            current_value=None,
            expected_source=src,
            blocks_pipeline=is_critical,
        ))
        return issues  # No further checks possible without a value.

    # ── Sign / negativity ───────────────────────────────────────────────────
    if not meta.get("allow_negative", True) and value < 0:
        issues.append(ValidationIssue(
            field=field,
            severity=SEVERITY_CRITICAL if is_critical else SEVERITY_WARNING,
            reason=(
                f"{field} is {value:,.2f}, which is negative. "
                f"This field should always be non-negative."
            ),
            current_value=value,
            expected_source=src,
            blocks_pipeline=is_critical,
        ))

    # ── Hard minimum ────────────────────────────────────────────────────────
    min_val = meta.get("min_value")
    if min_val is not None and value <= min_val and value >= 0:
        issues.append(ValidationIssue(
            field=field,
            severity=SEVERITY_WARNING,
            reason=(
                f"{field} is {value:,.2f}, at or below the expected minimum "
                f"of {min_val:,.2f}. This is unusual and may indicate stale "
                "or incorrectly scaled data."
            ),
            current_value=value,
            expected_source=src,
            blocks_pipeline=False,
        ))

    # ── Hard maximum ────────────────────────────────────────────────────────
    max_val = meta.get("max_value")
    if max_val is not None and value > max_val:
        issues.append(ValidationIssue(
            field=field,
            severity=SEVERITY_WARNING,
            reason=(
                f"{field} is {value:,.2f}, which exceeds the expected maximum "
                f"of {max_val:,.2f}."
            ),
            current_value=value,
            expected_source=src,
            blocks_pipeline=False,
        ))

    # ── Unit scale heuristic (likely reported in wrong unit) ────────────────
    # Values smaller than 100 are almost certainly misreported (e.g. in
    # billions when they should be in currency units).
    if field in {"market_cap", "revenue"} and 0 < value < 100:
        issues.append(ValidationIssue(
            field=field,
            severity=SEVERITY_WARNING,
            reason=(
                f"{field} = {value:,.4f} looks extremely small. "
                "Verify the unit: expected full currency units (not thousands "
                "or millions)."
            ),
            current_value=value,
            expected_source=src,
            blocks_pipeline=False,
        ))

    return issues


# ---------------------------------------------------------------------------
# Cross-field consistency checks
# ---------------------------------------------------------------------------

def _cross_field_issues(values: Dict[str, Optional[float]]) -> List[ValidationIssue]:
    """
    Validate relationships *between* fields.
    Runs after all individual field checks; only fires when both fields are
    non-None so as not to duplicate null-value errors.
    """
    issues: List[ValidationIssue] = []

    revenue      = values.get("revenue")
    net_income   = values.get("net_income")
    market_cap   = values.get("market_cap")
    cash         = values.get("cash")
    ocf          = values.get("operating_cash_flow")
    current_fcf  = values.get("current_fcf")
    norm_fcf     = values.get("normalized_fcf")

    # net_income must not exceed revenue (profit cannot exceed sales).
    if revenue and net_income is not None and net_income > revenue * MAX_NET_INCOME_TO_REVENUE_RATIO:
        issues.append(ValidationIssue(
            field="net_income",
            severity=SEVERITY_WARNING,
            reason=(
                f"net_income ({net_income:,.2f}) exceeds revenue "
                f"({revenue:,.2f}). Net income cannot exceed total revenue; "
                "this strongly suggests a data error."
            ),
            current_value=net_income,
            expected_source="income_value(data, NET_INCOME_KEYS)",
            blocks_pipeline=False,
        ))

    # current_fcf should not exceed operating_cash_flow by more than
    # MAX_FCF_OCF_EXCESS_FACTOR (FCF = OCF − capex; capex ≥ 0).
    if ocf is not None and current_fcf is not None:
        if current_fcf > ocf * MAX_FCF_OCF_EXCESS_FACTOR:
            issues.append(ValidationIssue(
                field="current_fcf",
                severity=SEVERITY_WARNING,
                reason=(
                    f"current_fcf ({current_fcf:,.2f}) exceeds "
                    f"operating_cash_flow ({ocf:,.2f}) × "
                    f"{MAX_FCF_OCF_EXCESS_FACTOR}. FCF = OCF − capex, so "
                    "FCF cannot exceed OCF unless capex is negative."
                ),
                current_value=current_fcf,
                expected_source="current_free_cash_flow(data)",
                blocks_pipeline=False,
            ))

    # Cash exceeding market_cap is extremely rare and usually a data error.
    if cash is not None and market_cap is not None and market_cap > 0:
        ratio = cash / market_cap
        if ratio > MAX_CASH_TO_MARKET_CAP_RATIO:
            issues.append(ValidationIssue(
                field="cash",
                severity=SEVERITY_WARNING,
                reason=(
                    f"cash ({cash:,.2f}) is {ratio:.1f}× market_cap "
                    f"({market_cap:,.2f}). This is extremely unusual and "
                    "may indicate a unit mismatch or stale market price."
                ),
                current_value=cash,
                expected_source="balance_value(data, CASH_KEYS)",
                blocks_pipeline=False,
            ))

    # normalized_fcf and current_fcf should be in the same ballpark.
    if current_fcf is not None and norm_fcf is not None and current_fcf != 0:
        ratio = abs(norm_fcf / current_fcf)
        if ratio > 10 or ratio < 0.1:
            issues.append(ValidationIssue(
                field="normalized_fcf",
                severity=SEVERITY_INFO,
                reason=(
                    f"normalized_fcf ({norm_fcf:,.2f}) differs from "
                    f"current_fcf ({current_fcf:,.2f}) by a factor of "
                    f"{ratio:.1f}×. Large divergence may indicate an "
                    "exceptional item or normalisation error."
                ),
                current_value=norm_fcf,
                expected_source="normalized_free_cash_flow(data)",
                blocks_pipeline=False,
            ))

    return issues


# ---------------------------------------------------------------------------
# Timeliness check
# ---------------------------------------------------------------------------

def _timeliness_issues(data: Dict[str, Any]) -> List[ValidationIssue]:
    """
    Check whether the financial data is fresh.
    Looks for a top-level ``data_as_of`` key (ISO-8601 date string or
    datetime / date object).
    """
    issues: List[ValidationIssue] = []
    raw = data.get("data_as_of")
    if raw is None:
        issues.append(ValidationIssue(
            field="data_as_of",
            severity=SEVERITY_INFO,
            reason=(
                "No 'data_as_of' timestamp found in the data payload. "
                "Cannot verify data freshness. Provide this key (ISO-8601 "
                "date string) for full timeliness validation."
            ),
            current_value=None,
            expected_source="data['data_as_of']",
            blocks_pipeline=False,
        ))
        return issues

    try:
        if isinstance(raw, (date, datetime)):
            as_of = raw if isinstance(raw, date) else raw.date()
        else:
            as_of = datetime.fromisoformat(str(raw)).date()
    except ValueError:
        issues.append(ValidationIssue(
            field="data_as_of",
            severity=SEVERITY_WARNING,
            reason=f"'data_as_of' value '{raw}' is not a valid ISO-8601 date.",
            current_value=None,
            expected_source="data['data_as_of']",
            blocks_pipeline=False,
        ))
        return issues

    age_days = (date.today() - as_of).days

    if age_days > STALE_DATA_BLOCK_DAYS:
        issues.append(ValidationIssue(
            field="data_as_of",
            severity=SEVERITY_CRITICAL,
            reason=(
                f"Data is {age_days} days old (as of {as_of}), which exceeds "
                f"the hard limit of {STALE_DATA_BLOCK_DAYS} days. "
                "Refresh the dataset before proceeding."
            ),
            current_value=None,
            expected_source="data['data_as_of']",
            blocks_pipeline=True,
        ))
    elif age_days > STALE_DATA_WARNING_DAYS:
        issues.append(ValidationIssue(
            field="data_as_of",
            severity=SEVERITY_WARNING,
            reason=(
                f"Data is {age_days} days old (as of {as_of}). "
                f"Consider refreshing — recommended freshness threshold is "
                f"{STALE_DATA_WARNING_DAYS} days."
            ),
            current_value=None,
            expected_source="data['data_as_of']",
            blocks_pipeline=False,
        ))

    return issues


# ---------------------------------------------------------------------------
# Core validation engine
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    """Structured output from the validation pipeline."""
    cleaned_values: Dict[str, Optional[float]] = field(default_factory=dict)
    issues: List[ValidationIssue] = field(default_factory=list)

    # Convenience properties ------------------------------------------------

    @property
    def critical_issues(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == SEVERITY_CRITICAL]

    @property
    def warning_issues(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == SEVERITY_WARNING]

    @property
    def blocking_issues(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.blocks_pipeline and not i.resolved]

    @property
    def needs_clarification(self) -> bool:
        return bool(self.critical_issues or self.warning_issues)

    @property
    def missing_critical(self) -> bool:
        return any(
            i.severity == SEVERITY_CRITICAL and i.current_value is None
            for i in self.issues
        )

    @property
    def action(self) -> str:
        if self.blocking_issues:
            return "REQUIRED_BEFORE_PROCEED"
        if self.needs_clarification:
            return "REVIEW_RECOMMENDED"
        return "OK"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action":              self.action,
            "needs_clarification": self.needs_clarification,
            "missing_critical":    self.missing_critical,
            "issues":              [i.to_dict() for i in self.issues],
            "cleaned_values":      self.cleaned_values,
        }


def _run_validation(data: Dict[str, Any]) -> ValidationResult:
    """
    Internal: run the full validation pipeline and return a ValidationResult.
    Does NOT prompt the user.
    """
    result = ValidationResult()

    # 1. Per-field checks.
    for field_name, meta in REQUIRED_FIELDS.items():
        raw   = meta["fetcher"](data)
        value = _to_number(raw)
        result.cleaned_values[field_name] = value

        for issue in _field_issues(field_name, value, meta):
            result.issues.append(issue)
            logger.debug("Field issue: %s", issue)

    # 2. Cross-field consistency checks.
    for issue in _cross_field_issues(result.cleaned_values):
        result.issues.append(issue)
        logger.debug("Cross-field issue: %s", issue)

    # 3. Timeliness checks.
    for issue in _timeliness_issues(data):
        result.issues.append(issue)
        logger.debug("Timeliness issue: %s", issue)

    return result


# ---------------------------------------------------------------------------
# Interactive resolver
# ---------------------------------------------------------------------------

# Default prompt callable: reads from stdin.
_DEFAULT_PROMPT: Callable[[str], str] = input


class InteractiveResolver:
    """
    Walks through every ValidationIssue that warrants user attention and
    prompts for a corrected value.

    Parameters
    ----------
    prompt_fn : callable(str) -> str
        Injectable prompt function (defaults to ``input``).
        Useful for GUI integration or automated tests.
    skip_info : bool
        If True, INFO-level issues are not presented to the user.
    allow_skip_warnings : bool
        If True, the user can press Enter to skip WARNING-level prompts
        and keep the original (possibly suspicious) value.
    """

    def __init__(
        self,
        prompt_fn: Callable[[str], str] = _DEFAULT_PROMPT,
        skip_info: bool = True,
        allow_skip_warnings: bool = True,
    ):
        self._prompt     = prompt_fn
        self._skip_info  = skip_info
        self._allow_skip = allow_skip_warnings

    # ------------------------------------------------------------------

    def _ask_for_value(
        self,
        issue: ValidationIssue,
        meta: Optional[Dict[str, Any]] = None,
    ) -> Optional[float]:
        """
        Display an issue to the user and collect a new numeric value.
        Returns the new value, or None if the user skips (warnings only).
        """
        description = meta.get("description", "") if meta else ""
        allow_neg   = meta.get("allow_negative", True) if meta else True

        separator = "-" * 60
        print(f"\n{separator}")
        print(f"  [{issue.severity}] Field: {issue.field.upper()}")
        if description:
            print(f"  What it is : {description}")
        print(f"  Problem    : {issue.reason}")
        print(f"  Source     : {issue.expected_source}")
        if issue.current_value is not None:
            print(f"  Current    : {issue.current_value:,.4f}")
        print(separator)

        skip_hint = " (or press Enter to keep current value)" if (
            self._allow_skip and issue.severity != SEVERITY_CRITICAL
        ) else ""

        while True:
            raw = self._prompt(
                f"  Enter corrected value for '{issue.field}'{skip_hint}: "
            ).strip()

            # Skip / keep existing (only for non-critical).
            if raw == "" and issue.severity != SEVERITY_CRITICAL:
                print(f"  → Skipped. Keeping current value: {issue.current_value}")
                return issue.current_value

            # Try to parse.
            num = _to_number(raw)
            if num is None:
                print("  ✗ Could not parse as a number. Please try again.")
                continue

            # Domain rule: field-specific negativity.
            if not allow_neg and num < 0:
                print(
                    f"  ✗ '{issue.field}' must be non-negative. "
                    f"You entered {num:,.4f}."
                )
                continue

            # Confirm the corrected value.
            confirm = self._prompt(
                f"  Confirm {issue.field} = {num:,.4f}? [Y/n]: "
            ).strip().lower()

            if confirm in ("", "y", "yes"):
                print(f"  ✓ Accepted {issue.field} = {num:,.4f}")
                return num

            print("  Re-entering…")

    # ------------------------------------------------------------------

    def resolve(self, result: ValidationResult) -> ValidationResult:
        """
        Iterate over all issues in *result* that require user attention,
        prompt for corrections, and return an updated ValidationResult.

        The original *result* object is mutated in place AND returned.
        """
        actionable = [
            i for i in result.issues
            if not (self._skip_info and i.severity == SEVERITY_INFO)
        ]

        if not actionable:
            print("\n✅ All financial inputs look valid. No user input required.")
            return result

        print(
            f"\n{'='*60}\n"
            f"  DATA QUALITY REVIEW — {len(actionable)} issue(s) found\n"
            f"  Action required: {result.action}\n"
            f"{'='*60}"
        )

        for issue in actionable:
            if issue.resolved:
                continue

            meta = REQUIRED_FIELDS.get(issue.field)

            new_value = self._ask_for_value(issue, meta)

            # Update the issue record.
            issue.resolved       = True
            issue.resolved_value = new_value

            # Push the corrected value back into cleaned_values if the field
            # is a known financial field (not e.g. data_as_of).
            if issue.field in result.cleaned_values:
                result.cleaned_values[issue.field] = new_value

        # Re-run cross-field checks with the corrected values so the caller
        # gets an up-to-date picture.
        post_cross = _cross_field_issues(result.cleaned_values)
        # Append only NEW issues (avoid duplicates).
        existing_fields = {(i.field, i.reason) for i in result.issues}
        for issue in post_cross:
            if (issue.field, issue.reason) not in existing_fields:
                result.issues.append(issue)

        print(
            f"\n{'='*60}\n"
            f"  REVIEW COMPLETE — Final action: {result.action}\n"
            f"{'='*60}\n"
        )

        return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_inputs(
    data: Dict[str, Any],
    *,
    interactive: bool = False,
    prompt_fn: Callable[[str], str] = _DEFAULT_PROMPT,
) -> Tuple[Dict[str, Optional[float]], Dict[str, Any]]:
    """
    Validate all required financial inputs.

    Parameters
    ----------
    data        : financial data payload (dict).
    interactive : if True, prompt the user to resolve missing/suspicious
                  values before returning.
    prompt_fn   : injectable prompt callable (used only when interactive=True).

    Returns
    -------
    cleaned_values : dict mapping field name → validated float (or None).
    review         : legacy-compatible dict with action, flags, questions.
    """
    result = _run_validation(data)

    if interactive and result.needs_clarification:
        resolver = InteractiveResolver(prompt_fn=prompt_fn)
        result   = resolver.resolve(result)

    # Build legacy-compatible review dict for callers that depend on it.
    review = _result_to_legacy_review(result)
    return result.cleaned_values, review


def validate_for_valuation(
    data: Dict[str, Any],
    *,
    interactive: bool = False,
    prompt_fn: Callable[[str], str] = _DEFAULT_PROMPT,
) -> Tuple[Dict[str, Optional[float]], Dict[str, Any]]:
    """
    Validation helper specifically for valuation logic.

    Identical to ``validate_inputs`` but applies valuation-safe defaults:
    - cash       defaults to 0 when still None after resolution
    - total_debt defaults to 0 when still None after resolution

    Parameters
    ----------
    data        : financial data payload.
    interactive : prompt user to fill in null / suspicious values.
    prompt_fn   : injectable prompt callable.

    Returns
    -------
    cleaned_values : validated floats with valuation-safe defaults applied.
    review         : legacy-compatible review dict.
    """
    cleaned_values, review = validate_inputs(
        data, interactive=interactive, prompt_fn=prompt_fn
    )

    # Apply valuation-safe defaults only *after* any interactive resolution.
    if cleaned_values.get("cash") is None:
        logger.info("cash defaulted to 0 for valuation.")
        cleaned_values["cash"] = 0.0

    if cleaned_values.get("total_debt") is None:
        logger.info("total_debt defaulted to 0 for valuation.")
        cleaned_values["total_debt"] = 0.0

    return cleaned_values, review


def validate_and_resolve(
    data: Dict[str, Any],
    prompt_fn: Callable[[str], str] = _DEFAULT_PROMPT,
) -> ValidationResult:
    """
    Full pipeline: validate then interactively resolve all issues.

    Returns the rich ``ValidationResult`` object (not the legacy dict tuple)
    so callers can inspect individual issues, severities, and resolutions.
    """
    result   = _run_validation(data)
    resolver = InteractiveResolver(prompt_fn=prompt_fn)
    return resolver.resolve(result)


def positive_denominator(value: Any) -> Optional[float]:
    """
    Public helper for valuation ratios.
    Returns a valid strictly-positive float, or None.
    """
    return _positive_number(value)


# ---------------------------------------------------------------------------
# Legacy review builder  (keeps backward compatibility)
# ---------------------------------------------------------------------------

def _result_to_legacy_review(result: ValidationResult) -> Dict[str, Any]:
    """
    Convert a ValidationResult into the original review dict shape so that
    existing callers require no changes.
    """
    questions = []
    flags     = []

    for issue in result.issues:
        entry = {
            "field":           issue.field,
            "reason":          issue.reason,
            "expected_source": issue.expected_source,
            "critical":        issue.severity == SEVERITY_CRITICAL,
        }
        if issue.severity in (SEVERITY_CRITICAL, SEVERITY_WARNING):
            questions.append(entry)
        if issue.current_value is not None and issue.severity == SEVERITY_WARNING:
            flags.append({
                **entry,
                "value": issue.current_value,
            })

    return {
        "needs_clarification": result.needs_clarification,
        "missing_critical":    result.missing_critical,
        "questions":           questions,
        "flags":               flags,
        "action":              result.action,
    }


def build_valuation_review_message(review: Dict[str, Any]) -> str:
    """
    Convert a legacy review dict into a human-readable string.
    Suitable for logs or simple CLI display.
    """
    if not review:
        return "No review information available."

    if not review.get("needs_clarification"):
        return "✅ All required inputs look valid."

    lines = [f"Action : {review.get('action', 'REVIEW')}"]

    questions = review.get("questions", [])
    if questions:
        lines.append("\nClarification needed:")
        for item in questions:
            crit  = "🔴 CRITICAL" if item["critical"] else "🟡 WARNING"
            lines.append(
                f"  {crit}  {item['field']}: {item['reason']}\n"
                f"           source: {item['expected_source']}"
            )

    flags = review.get("flags", [])
    if flags:
        lines.append("\nSuspicious values:")
        for item in flags:
            lines.append(
                f"  ⚠️  {item['field']} = {item['value']:,.4f} "
                f"(source: {item['expected_source']})"
            )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Valuation ratio computation
# ---------------------------------------------------------------------------

# Sentinel used in the output dict to signal a ratio could not be computed.
_NA = None


def _safe_ratio(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    """
    Divide numerator by denominator, returning None on any invalid input:
    None operands, zero / negative denominator, or non-finite result.
    """
    if numerator is None or denominator is None:
        return None
    if not isfinite(numerator) or not isfinite(denominator):
        return None
    if denominator == 0:
        return None
    result = numerator / denominator
    return result if isfinite(result) else None


def _enterprise_value(
    market_cap: Optional[float],
    total_debt: Optional[float],
    cash: Optional[float],
) -> Optional[float]:
    """
    EV = Market Cap + Total Debt − Cash.
    Returns None if market_cap is unavailable (debt and cash default to 0).
    """
    if market_cap is None:
        return None
    debt = total_debt if total_debt is not None else 0.0
    csh  = cash       if cash       is not None else 0.0
    ev   = market_cap + debt - csh
    return ev if isfinite(ev) else None


@dataclass
class ValuationOutput:
    """
    Structured container for all computed valuation ratios and metadata.

    All ratio fields are Optional[float].  None means the ratio could not
    be computed (missing / invalid inputs) — it is NOT zero.

    Fields
    ------
    ticker          : stock symbol, if provided in the source data.
    data_as_of      : date the underlying financials relate to.
    computed_at     : UTC timestamp when compute_valuation() ran.

    Multiples
    ---------
    pe_ratio        : Price-to-Earnings  = market_cap / net_income
    ps_ratio        : Price-to-Sales     = market_cap / revenue
    pb_ratio        : Price-to-Book      = market_cap / equity
    ev              : Enterprise Value   = market_cap + debt − cash
    ev_to_revenue   : EV / Revenue
    ev_to_fcf       : EV / normalized_fcf  (preferred for DCF cross-check)
    ev_to_ocf       : EV / operating_cash_flow
    price_to_fcf    : market_cap / current_fcf
    roe             : Return on Equity   = net_income / equity
    profit_margin   : net_income / revenue
    debt_to_equity  : total_debt / equity
    cash_ratio      : cash / market_cap

    Data quality
    ------------
    review_action   : "OK" | "REVIEW_RECOMMENDED" | "REQUIRED_BEFORE_PROCEED"
    issues          : list of ValidationIssue dicts for inspection / logging.
    skipped_ratios  : list of ratio names that could not be computed with reasons.
    """
    # Identity
    ticker:          Optional[str]   = None
    data_as_of:      Optional[str]   = None
    computed_at:     str             = ""

    # Core inputs (validated)
    market_cap:           Optional[float] = None
    net_income:           Optional[float] = None
    revenue:              Optional[float] = None
    equity:               Optional[float] = None
    cash:                 Optional[float] = None
    total_debt:           Optional[float] = None
    operating_cash_flow:  Optional[float] = None
    current_fcf:          Optional[float] = None
    normalized_fcf:       Optional[float] = None

    # Derived multiples
    pe_ratio:       Optional[float] = None
    ps_ratio:       Optional[float] = None
    pb_ratio:       Optional[float] = None
    ev:             Optional[float] = None
    ev_to_revenue:  Optional[float] = None
    ev_to_fcf:      Optional[float] = None
    ev_to_ocf:      Optional[float] = None
    price_to_fcf:   Optional[float] = None
    roe:            Optional[float] = None
    profit_margin:  Optional[float] = None
    debt_to_equity: Optional[float] = None
    cash_ratio:     Optional[float] = None

    # Data-quality metadata
    review_action:  str              = "OK"
    issues:         List[Dict]       = field(default_factory=list)
    skipped_ratios: List[Dict]       = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Return a plain dict — convenient for JSON serialisation or DataFrames."""
        return {k: v for k, v in self.__dict__.items()}



def compute_valuation(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute 10 focused valuation metrics.

    Three design choices
    --------------------
    1. Normalized earnings
       PE and Earnings_Yield use a multi-year average of positive net income
       rather than a single TTM figure.  Single-year earnings are volatile due
       to write-downs, tax windfalls, and one-off items; the average gives a
       truer picture of the company's earnings power.

    2. PB and P_TBV removed
       Both ratios are unreliable outside financial/asset-heavy sectors and
       heavily distorted by buybacks, intangible-heavy business models, and
       varying amortisation policies.

    3. Growth-adjusted multiples
       PEG   = Normalized PE  / EPS growth %
       EV_Sales_G = (EV/Sales) / Revenue growth %
       Both collapse to None when growth is zero or negative to avoid
       producing a misleading sign inversion.

    Metrics returned
    ----------------
    PE              Normalized Price-to-Earnings
    PS              Price-to-Sales
    P_CF            Price-to-Operating-Cash-Flow
    PEG             Normalized PE / EPS growth %
    EV_EBITDA       Enterprise Value / EBITDA
    EV_Sales        Enterprise Value / Revenue
    EV_Sales_G      EV/Sales divided by Revenue growth %  (growth-adjusted)
    P_EBITDA        Market Cap / EBITDA
    Cash_Earnings_Yield   (OCF − Preferred Dividends) / Market Cap
    Dividend_Yield  Annual dividends / Market Cap
    Earnings_Yield  Normalized Net Income / Market Cap
    """

    # ── helpers ─────────────────────────────────────────────────────────────

    def _v(x: Any) -> Optional[float]:
        if is_missing(x) or x is None:
            return None
        try:
            f = float(x)
        except (TypeError, ValueError):
            return None
        return f if isfinite(f) else None

    def _pos(x: Any) -> Optional[float]:
        v = _v(x)
        return v if (v is not None and v > 0) else None

    def _ratio(num: Any, den: Any) -> Optional[float]:
        try:
            r = _v(safe_div(num, den))
            return r
        except Exception:
            n, d = _v(num), _v(den)
            if n is None or d is None or d == 0:
                return None
            r = n / d
            return r if isfinite(r) else None

    # ── 1. Raw inputs ────────────────────────────────────────────────────────

    info       = data.get("info", {}) if isinstance(data.get("info"), dict) else {}
    market_cap = _v(market_cap_value(info))
    revenue    = _v(income_value(data, REVENUE_KEYS))
    net_income = _v(income_value(data, NET_INCOME_KEYS))   # TTM (fallback only)
    cash_val   = _v(balance_value(data, CASH_KEYS)) or 0.0
    total_debt = _v(total_debt_value(data)) or 0.0
    ocf        = _v(cashflow_value(data, OPERATING_CASH_FLOW_KEYS))

    # D&A — for EBITDA reconstruction
    _da_keys = ("depreciation", "depreciationAndAmortization",
                "Depreciation & Amortization", "Depreciation")
    da: Optional[float] = None
    for k in _da_keys:
        v = _v(cashflow_value(data, [k])) or _v(info.get(k))
        if v is not None:
            da = abs(v)
            break

    # Operating income — for EBITDA reconstruction
    _op_keys = ("operatingIncome", "ebit", "OperatingIncome", "Operating Income", "EBIT")
    operating_income: Optional[float] = None
    for k in _op_keys:
        v = _v(income_value(data, [k])) or _v(info.get(k))
        if v is not None:
            operating_income = v
            break

    # Tax & interest — for EBITDA build-up
    tax: Optional[float] = None
    for k in ("incomeTaxExpense", "Tax Provision"):
        v = _v(info.get(k)) or _v(income_value(data, [k]))
        if v is not None:
            tax = v
            break

    interest: Optional[float] = None
    for k in ("interestExpense", "Interest Expense"):
        v = _v(info.get(k)) or _v(income_value(data, [k]))
        if v is not None:
            interest = abs(v)
            break

    # Preferred dividends — deducted from OCF for cash earnings yield
    pref_div: Optional[float] = None
    for k in ("preferredDividends", "Preferred Dividends"):
        v = _v(cashflow_value(data, [k])) or _v(info.get(k))
        if v is not None:
            pref_div = abs(v)
            break

    # Growth rates
    eps_growth = _v(
        info.get("earningsQuarterlyGrowth")
        or info.get("earningsGrowth")
        or info.get("epsGrowth")
    )
    rev_growth = _v(
        info.get("revenueGrowth")
        or info.get("Revenue_Growth")
        or data.get("Revenue_Growth")
    )

    # Dividend yield (already a ratio from provider)
    dividend_yield = _v(
        info.get("dividendYield") or info.get("trailingAnnualDividendYield")
    )

    # ── 2. Normalized earnings ───────────────────────────────────────────────
    #
    # Build a multi-year earnings series from whichever history key the data
    # feed supplies, then take the average of all *positive* years.
    # Averaging over positive years only avoids letting a single extraordinary
    # loss crater the denominator; it reflects sustainable earnings power.
    #
    # Sources tried in order:
    #   (a) data["net_income_history"]  – list of annual net income values
    #   (b) data["earnings_history"]    – same alternate key
    #   (c) financials DataFrame annual rows (yfinance-style)
    #   (d) TTM net_income alone        – last resort, single point
    #
    ni_series: List[float] = []

    for key in ("net_income_history", "earnings_history", "netIncomeHistory"):
        raw = data.get(key) or info.get(key)
        if isinstance(raw, (list, tuple)):
            ni_series = [_v(x) for x in raw if _v(x) is not None]
            break

    # Try a financials DataFrame / dict-of-dicts (yfinance annual_financials)
    if not ni_series:
        fin = data.get("financials") or data.get("annual_financials")
        if isinstance(fin, dict):
            for ni_key in NET_INCOME_KEYS:
                row = fin.get(ni_key)
                if isinstance(row, dict):
                    ni_series = [_v(v) for v in row.values() if _v(v) is not None]
                    break

    # Fallback: single TTM value
    if not ni_series and net_income is not None:
        ni_series = [net_income]

    # Average of positive years → normalized earnings
    positive_ni = [x for x in ni_series if x is not None and x > 0]
    normalized_earnings: Optional[float] = (
        sum(positive_ni) / len(positive_ni) if positive_ni else None
    )

    # ── 3. EBITDA — three-tier reconstruction ────────────────────────────────
    ebitda: Optional[float] = _v(info.get("ebitda") or info.get("EBITDA"))

    if ebitda is None and operating_income is not None and da is not None:
        ebitda = operating_income + da

    if ebitda is None and net_income is not None and da is not None:
        build = net_income + da
        if tax      is not None: build += tax
        if interest is not None: build += interest
        ebitda = build

    # ── 4. Enterprise Value ──────────────────────────────────────────────────
    enterprise_value: Optional[float] = None
    if market_cap is not None:
        enterprise_value = market_cap + total_debt - cash_val

    pos_ev = enterprise_value if (enterprise_value is not None and enterprise_value > 0) else None

    # ── 5. Growth rates as percentage points ─────────────────────────────────
    #
    # Providers store growth as decimals (0.15 = 15 %).  PEG and EV_Sales_G
    # need percentage points.  We detect the encoding by magnitude.
    #
    def _to_pct(g: Optional[float]) -> Optional[float]:
        if g is None:
            return None
        return g * 100 if abs(g) <= 5 else g   # already in pct if > 5

    eps_growth_pct = _to_pct(eps_growth)
    rev_growth_pct = _to_pct(rev_growth)

    # ── 6. The 10 metrics ────────────────────────────────────────────────────

    # Normalized P/E
    pe = _ratio(market_cap, normalized_earnings)   # None when all years are losses

    # P/S
    ps = _ratio(market_cap, _pos(revenue))

    # P/CF  (suppressed for negative OCF)
    p_cf = _ratio(market_cap, _pos(ocf))

# ── MODIFICATION 1: Adjusted PEG ─────────────────────────────────────────
    peg: Optional[float] = None
    
    if pe is not None and eps_growth_pct is not None:
        # Only calculate PEG if growth is strictly positive.
        # Clamping negative/zero growth to a floor of 1 mathematically forces PEG = PE, 
        # which misrepresents shrinking companies.
        if eps_growth_pct > 0:
            peg = _ratio(pe, eps_growth_pct)
        else:
            # PEG is traditionally N/A (None) for zero or negative growth 
            # because the multiple becomes meaningless.
            peg = None
    # EV/EBITDA  (suppressed when EBITDA ≤ 0)
    ev_ebitda = _ratio(pos_ev, _pos(ebitda))

    # EV/Sales
    ev_sales = _ratio(pos_ev, _pos(revenue))

    # EV/Sales growth-adjusted = (EV/Sales) / Revenue growth %
    # Analogous to PEG but at the enterprise level — compares valuation to
    # the rate at which the top line is expanding.
    ev_sales_g: Optional[float] = None
    if ev_sales is not None and rev_growth_pct is not None and rev_growth_pct > 0:
        ev_sales_g = _ratio(ev_sales, rev_growth_pct)

    # P/EBITDA
    p_ebitda = _ratio(market_cap, _pos(ebitda))

    # Cash Earnings Yield = (OCF − Preferred Dividends) / Market Cap
    cash_earnings_yield: Optional[float] = None
    if ocf is not None and market_cap is not None and market_cap > 0:
        cash_earnings_yield = _ratio(ocf - (pref_div or 0.0), market_cap)

    # Normalized Earnings Yield (inverse of normalized P/E)
    earnings_yield: Optional[float] = None
    if normalized_earnings is not None and market_cap is not None and market_cap > 0:
        earnings_yield = _ratio(normalized_earnings, market_cap)

    # ── MODIFICATION 2 & 3: Advanced Scoring & Normalization ─────────────────
    valuation_score = 50.0  # Starting baseline score
    pe_weight = 1.0
    
    # 2. Margin expansion factor
    # Attempt to fetch margin trend from data feed, default to 0
    operating_margin_trend = _v(info.get("operatingMarginTrend") or data.get("operating_margin_trend")) or 0.0
    margin_expansion_boost = 15.0  # Configurable boost amount
    
    if operating_margin_trend > 0:
        valuation_score += margin_expansion_boost

    # 3. Earnings normalization flag
    # Heuristic: If raw net income is > 20% higher than the multi-year normalized 
    # earnings, assume one-time gains are heavily skewing the current year.
    one_time_gains_present = False
    if net_income is not None and normalized_earnings is not None:
        if net_income > (normalized_earnings * 1.2):
            one_time_gains_present = True

    if one_time_gains_present or info.get("oneTimeGainsPresent"):
        pe_weight -= 0.5  # Downgrade PE weight for downstream aggregation logic


    # ── 7. Return ────────────────────────────────────────────────────────────

    metrics: Dict[str, Any] = {
        "PE":                  pe,
        "PS":                  ps,
        "P_CF":                p_cf,
        "PEG":                 peg,
        "EV_EBITDA":           ev_ebitda,
        "EV_Sales":            ev_sales,
        "EV_Sales_G":          ev_sales_g,
        "P_EBITDA":            p_ebitda,
        "Cash_Earnings_Yield": cash_earnings_yield,
        "Dividend_Yield":      dividend_yield,
        "Earnings_Yield":      earnings_yield,
        # Append new metrics to the output
        "Valuation_Score":     valuation_score,
        "PE_Weight":           pe_weight,
        "One_Time_Gains_Flag": one_time_gains_present,
    }

    return {key: normalize_output(value) for key, value in metrics.items()}