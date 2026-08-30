from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Iterable

from . import _core
from .models import IntegrityAudit, IntegrityIssue, Observation, to_primitive


def configuration_fingerprint(configuration: dict[str, Any]) -> str:
    canonical = json.dumps(
        to_primitive(configuration),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def eligible_observations(
    observations: Iterable[Observation], decision_cutoff_ms: int
) -> tuple[Observation, ...]:
    return tuple(
        observation
        for observation in observations
        if observation.timestamp_ms <= decision_cutoff_ms
        and observation.available_at_ms <= decision_cutoff_ms
    )


def as_native_bars(observations: Iterable[Observation]) -> list[_core.Bar]:
    bars: list[_core.Bar] = []
    for observation in observations:
        bar = _core.Bar()
        bar.timestamp_ms = observation.timestamp_ms
        bar.available_at_ms = observation.available_at_ms
        bar.close = observation.close
        bar.volume = observation.volume
        bar.realized_volatility = observation.realized_volatility
        bar.liquidity = observation.liquidity
        bars.append(bar)
    return bars


def validate_post_cutoff_observations(
    observations: Iterable[Observation], decision_cutoff_ms: int
) -> tuple[Observation, ...]:
    evaluation = tuple(observations)
    if not evaluation:
        raise ValueError("Evaluation partition must contain at least one observation")
    previous_timestamp: int | None = None
    for observation in evaluation:
        if observation.timestamp_ms <= decision_cutoff_ms:
            raise ValueError(
                "Evaluation data must begin and remain strictly after the decision cutoff"
            )
        if observation.available_at_ms < observation.timestamp_ms:
            raise ValueError(
                "Evaluation observation available_at must not precede timestamp"
            )
        if (
            previous_timestamp is not None
            and observation.timestamp_ms <= previous_timestamp
        ):
            raise ValueError(
                "Evaluation observation timestamps must be strictly increasing"
            )
        if not all(
            math.isfinite(value)
            for value in (
                observation.close,
                observation.volume,
                observation.realized_volatility,
                observation.liquidity,
            )
        ):
            raise ValueError("Evaluation market fields must be finite numeric values")
        if (
            observation.close <= 0.0
            or observation.volume < 0.0
            or observation.realized_volatility < 0.0
            or observation.liquidity < 0.0
        ):
            raise ValueError("Evaluation market values are invalid")
        previous_timestamp = observation.timestamp_ms
    return evaluation


def build_integrity_audit(
    observations: Iterable[Observation],
    decision_cutoff_ms: int,
    configuration: dict[str, Any],
    minimum_points: int = 4,
    universe_id: str | None = None,
    survivorship_controlled: bool = False,
    rebalance_timing: str = "not_applicable_research_only",
) -> IntegrityAudit:
    provided = tuple(observations)
    eligible = eligible_observations(provided, decision_cutoff_ms)
    future_timestamp_count = sum(
        1 for item in provided if item.timestamp_ms > decision_cutoff_ms
    )
    unavailable_count = sum(
        1
        for item in provided
        if item.timestamp_ms <= decision_cutoff_ms
        and item.available_at_ms > decision_cutoff_ms
    )
    native = _core.inspect_integrity(
        as_native_bars(provided), decision_cutoff_ms, minimum_points
    )
    issues = tuple(
        IntegrityIssue(item.code, item.severity, item.message) for item in native.issues
    )
    warnings: list[str] = []
    leakage_flags: list[str] = []
    if future_timestamp_count:
        warnings.append(
            f"Excluded {future_timestamp_count} observations with timestamps after the decision cutoff from feature access"
        )
        leakage_flags.append("future_timestamp_access_prevented")
    if unavailable_count:
        warnings.append(
            f"Excluded {unavailable_count} observations that were unavailable at the decision cutoff"
        )
        leakage_flags.append("availability_timestamp_access_prevented")
    if universe_id is None:
        warnings.append(
            "No historical universe identifier was supplied; survivorship status cannot be independently verified"
        )
    if not survivorship_controlled:
        warnings.append(
            "Survivorship control was not declared; historical conclusions may be affected by universe selection bias"
        )
    if rebalance_timing != "not_applicable_research_only":
        warnings.append(
            "Rebalance timing is recorded for research chronology only and does not produce trading instructions"
        )
    integrity_configuration = {
        "configuration": configuration,
        "decision_cutoff_ms": decision_cutoff_ms,
        "minimum_points": minimum_points,
        "universe_id": universe_id,
        "survivorship_controlled": survivorship_controlled,
        "rebalance_timing": rebalance_timing,
    }
    return IntegrityAudit(
        valid=bool(native.valid),
        decision_cutoff_ms=decision_cutoff_ms,
        provided_input_count=len(provided),
        eligible_input_count=len(eligible),
        excluded_future_timestamp_count=future_timestamp_count,
        excluded_unavailable_count=unavailable_count,
        feature_window_start_ms=eligible[0].timestamp_ms if eligible else None,
        feature_window_end_ms=eligible[-1].timestamp_ms if eligible else None,
        rebalance_timing=rebalance_timing,
        universe_id=universe_id,
        survivorship_controlled=survivorship_controlled,
        chronology_check="passed" if native.valid else "failed",
        leakage_flags=tuple(leakage_flags),
        warnings=tuple(warnings),
        issues=issues,
        configuration_fingerprint=configuration_fingerprint(integrity_configuration),
    )
