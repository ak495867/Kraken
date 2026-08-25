from __future__ import annotations

from typing import Iterable

from .models import CorporateAction, CorporateActionIntegrityReport, IntegrityIssue, Observation, OptionContractAdjustment, OptionQuote


def validate_corporate_action_integrity(
    equity: Iterable[Observation],
    options: Iterable[OptionQuote],
    corporate_actions: Iterable[CorporateAction],
    option_adjustments: Iterable[OptionContractAdjustment],
    decision_cutoff_ms: int,
    price_basis: str,
) -> CorporateActionIntegrityReport:
    bars = tuple(equity)
    quotes = tuple(options)
    actions = tuple(corporate_actions)
    adjustments = tuple(option_adjustments)
    normalized_basis = price_basis.strip().lower()
    if normalized_basis not in {"raw", "split_adjusted"}:
        raise ValueError("price_basis must be raw or split_adjusted")
    issues: list[IntegrityIssue] = []
    warnings: list[str] = []
    known_actions = tuple(action for action in actions if action.effective_at_ms <= decision_cutoff_ms)
    checked_options = tuple(quote for quote in quotes if quote.timestamp_ms <= decision_cutoff_ms)
    for action in known_actions:
        if action.available_at_ms > decision_cutoff_ms:
            issues.append(IntegrityIssue("corporate_action_availability_leakage", "error", "Corporate action was not available at the decision cutoff"))
            continue
        matching = tuple(
            adjustment
            for adjustment in adjustments
            if adjustment.underlying == action.underlying and adjustment.effective_at_ms == action.effective_at_ms and adjustment.available_at_ms <= decision_cutoff_ms
        )
        if not matching:
            issues.append(IntegrityIssue("missing_option_split_adjustment", "error", "Known stock or reverse split has no known matching option-contract adjustment"))
            continue
        expected_strike_factor = 1.0 / action.factor
        expected_multiplier_factor = action.factor
        if not any(
            abs(adjustment.strike_factor - expected_strike_factor) <= 1e-9 and abs(adjustment.multiplier_factor - expected_multiplier_factor) <= 1e-9
            for adjustment in matching
        ):
            issues.append(IntegrityIssue("option_split_factor_mismatch", "error", "Option-contract split factors do not match the recorded corporate-action factor"))
    if normalized_basis == "raw":
        for action in known_actions:
            before = next((bar for bar in reversed(bars) if bar.timestamp_ms < action.effective_at_ms), None)
            after = next((bar for bar in bars if bar.timestamp_ms >= action.effective_at_ms), None)
            if before is None or after is None:
                warnings.append("Raw-price split validation could not locate observations on both sides of a known action")
                continue
            expected_ratio = 1.0 / action.factor
            observed_ratio = after.close / before.close
            if abs(observed_ratio - expected_ratio) > max(0.25 * expected_ratio, 0.01):
                warnings.append("Raw-price movement around a known split differs materially from the declared factor; inspect vendor price basis")
    else:
        warnings.append("Split-adjusted equity prices are not re-scaled by Kraken; option-contract adjustment records remain independently validated")
    if not known_actions:
        warnings.append("No corporate actions were supplied at this decision cutoff; split validation is limited to absence-of-record checks")
    return CorporateActionIntegrityReport(
        valid=not any(issue.severity == "error" for issue in issues),
        decision_cutoff_ms=decision_cutoff_ms,
        checked_action_count=len(known_actions),
        checked_option_count=len(checked_options),
        known_split_count=len(known_actions),
        warnings=tuple(warnings),
        issues=tuple(issues),
    )
