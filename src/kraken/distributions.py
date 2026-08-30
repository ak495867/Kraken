from __future__ import annotations

from typing import Iterable

from .models import (
    DistributionIntegrityReport,
    DistributionRecord,
    IntegrityIssue,
    Observation,
)


def validate_distribution_integrity(
    equity: Iterable[Observation],
    distributions: Iterable[DistributionRecord],
    decision_cutoff_ms: int,
    price_basis: str,
) -> DistributionIntegrityReport:
    bars = tuple(equity)
    records = tuple(distributions)
    normalized_basis = price_basis.strip().lower()
    if normalized_basis not in {"raw", "split_adjusted"}:
        raise ValueError("price_basis must be raw or split_adjusted")
    known = tuple(
        record for record in records if record.effective_at_ms <= decision_cutoff_ms
    )
    issues: list[IntegrityIssue] = []
    warnings: list[str] = []
    seen: set[tuple[int, str, str, float]] = set()
    for record in known:
        identity = (
            record.effective_at_ms,
            record.underlying,
            record.distribution_type,
            record.amount,
        )
        if identity in seen:
            issues.append(
                IntegrityIssue(
                    "duplicate_distribution_record",
                    "error",
                    "Distribution records must be unique by effective date, underlying, type, and amount",
                )
            )
            continue
        seen.add(identity)
        if record.available_at_ms > decision_cutoff_ms:
            issues.append(
                IntegrityIssue(
                    "distribution_availability_leakage",
                    "error",
                    "Cash dividend or special distribution was not available at the decision cutoff",
                )
            )
    if normalized_basis == "raw":
        for record in known:
            before = next(
                (
                    bar
                    for bar in reversed(bars)
                    if bar.timestamp_ms < record.effective_at_ms
                ),
                None,
            )
            after = next(
                (bar for bar in bars if bar.timestamp_ms >= record.effective_at_ms),
                None,
            )
            if before is None or after is None:
                warnings.append(
                    "Raw-price distribution validation could not locate observations on both sides of a known distribution"
                )
                continue
            observed_drop = before.close - after.close
            if observed_drop < -0.05 * max(record.amount, 1.0):
                warnings.append(
                    "Raw-price movement around a known distribution is directionally inconsistent; inspect vendor adjustment conventions"
                )
    else:
        warnings.append(
            "Split-adjusted price basis does not permit direct cash-distribution drop validation; point-in-time availability and record uniqueness remain enforced"
        )
    if not known:
        warnings.append(
            "No cash dividends or special distributions were supplied at this decision cutoff"
        )
    return DistributionIntegrityReport(
        valid=not any(issue.severity == "error" for issue in issues),
        decision_cutoff_ms=decision_cutoff_ms,
        checked_distribution_count=len(records),
        known_distribution_count=len(known),
        warnings=tuple(warnings),
        issues=tuple(issues),
    )
