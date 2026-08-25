from __future__ import annotations

import math
from dataclasses import replace
from typing import Iterable, Sequence

from .analysis import DEFAULT_HORIZONS, analyze_regime_risk
from .audit import configuration_fingerprint, validate_post_cutoff_observations
from .models import Observation, WalkForwardReport, WalkForwardWindow
from .provenance import create_run_manifest


def run_walk_forward(
    observations: Iterable[Observation],
    train_size: int,
    validation_size: int,
    test_size: int,
    embargo_size: int = 1,
    horizons: Sequence[int] = DEFAULT_HORIZONS,
    universe_id: str | None = None,
    survivorship_controlled: bool = False,
) -> WalkForwardReport:
    series = tuple(observations)
    if min(train_size, validation_size, test_size) <= 0 or embargo_size < 1:
        raise ValueError("train_size, validation_size, and test_size must be positive and embargo_size must be at least one")
    required = train_size + validation_size + test_size + 2 * embargo_size
    if len(series) < required:
        raise ValueError("Input does not contain enough observations for one embargoed walk-forward window")
    windows: list[WalkForwardWindow] = []
    window_id = 1
    start = 0
    while start + required <= len(series):
        train = series[start : start + train_size]
        validation_start = start + train_size + embargo_size
        validation = series[validation_start : validation_start + validation_size]
        test_start = validation_start + validation_size + embargo_size
        test = series[test_start : test_start + test_size]
        cutoff = validation[-1].available_at_ms
        history = train + validation
        report = analyze_regime_risk(
            history,
            cutoff,
            horizons=horizons,
            reference_size=len(train),
            universe_id=universe_id,
            survivorship_controlled=survivorship_controlled,
        )
        test = validate_post_cutoff_observations(test, cutoff)
        realized_log_return = math.log(test[-1].close / validation[-1].close)
        windows.append(
            WalkForwardWindow(
                window_id=window_id,
                train_start_ms=train[0].timestamp_ms,
                train_end_ms=train[-1].timestamp_ms,
                validation_start_ms=validation[0].timestamp_ms,
                validation_end_ms=validation[-1].timestamp_ms,
                decision_cutoff_ms=cutoff,
                evaluation_start_ms=test[0].timestamp_ms,
                evaluation_end_ms=test[-1].timestamp_ms,
                regime=report.regime,
                confidence=report.confidence,
                uncertainty=report.uncertainty,
                realized_log_return=realized_log_return,
                integrity=report.integrity,
            )
        )
        window_id += 1
        start += test_size
    configuration = {
        "analysis": "walk_forward",
        "train_size": train_size,
        "validation_size": validation_size,
        "test_size": test_size,
        "embargo_size": embargo_size,
        "horizons": tuple(int(item) for item in horizons),
        "universe_id": universe_id,
        "survivorship_controlled": survivorship_controlled,
    }
    warnings = (
        "Evaluation returns are reported after each embargoed decision cutoff and are not available to feature computation",
        "Walk-forward output is research-only and does not provide trading instructions",
    )
    result = WalkForwardReport(
        configuration_fingerprint=configuration_fingerprint(configuration),
        train_size=train_size,
        validation_size=validation_size,
        test_size=test_size,
        embargo_size=embargo_size,
        windows=tuple(windows),
        warnings=warnings,
    )
    manifest = create_run_manifest(
        configuration,
        {"observations": series},
        result,
        result.windows[-1].decision_cutoff_ms if result.windows else None,
        warnings=result.warnings,
    )
    return replace(result, manifest=manifest)
