from __future__ import annotations

from typing import Iterable

from .models import EarningsEvent, EarningsIntegrityReport, IntegrityIssue


def validate_earnings_event_integrity(
    events: Iterable[EarningsEvent],
    decision_cutoff_ms: int,
) -> EarningsIntegrityReport:
    records = tuple(events)
    known = tuple(event for event in records if event.event_at_ms <= decision_cutoff_ms)
    issues: list[IntegrityIssue] = []
    warnings: list[str] = []
    seen: set[tuple[int, str, str, str]] = set()
    for event in known:
        identity = (event.event_at_ms, event.underlying, event.fiscal_period, event.event_type)
        if identity in seen:
            issues.append(IntegrityIssue("duplicate_earnings_event", "error", "Earnings events must be unique by event time, underlying, fiscal period, and type"))
            continue
        seen.add(identity)
        if event.available_at_ms > decision_cutoff_ms:
            issues.append(IntegrityIssue("earnings_availability_leakage", "error", "Earnings event was not available at the decision cutoff"))
    if not known:
        warnings.append("No earnings events were supplied at this decision cutoff")
    return EarningsIntegrityReport(
        valid=not any(issue.severity == "error" for issue in issues),
        decision_cutoff_ms=decision_cutoff_ms,
        checked_event_count=len(records),
        known_event_count=len(known),
        warnings=tuple(warnings),
        issues=tuple(issues),
    )
