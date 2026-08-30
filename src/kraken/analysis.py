from dataclasses import replace
from typing import Iterable, Sequence

from . import _core
from .audit import as_native_bars, build_integrity_audit, eligible_observations
from .config_runtime import resolve_research_config
from .models import (
    DistanceCalibrationReport,
    Echo,
    ForecastBand,
    Observation,
    RegimeRiskReport,
    SonarReport,
)
from .provenance import create_run_manifest

DEFAULT_HORIZONS = (1, 5, 10)


def _validate_horizons(horizons: Sequence[int]) -> tuple[int, ...]:
    parsed = tuple(int(value) for value in horizons)
    if not parsed or any(value <= 0 for value in parsed):
        raise ValueError("At least one positive integer horizon is required")
    if len(set(parsed)) != len(parsed):
        raise ValueError("Horizons must be unique")
    return parsed


def _sonar_report(native: _core.SonarResult, cutoff: int, audit) -> SonarReport:
    return SonarReport(
        decision_cutoff_ms=cutoff,
        input_count=audit.eligible_input_count,
        signal_strength=native.signal_strength,
        anomaly_score=native.anomaly_score,
        echoes=tuple(
            Echo(item.horizon, item.displacement, item.strength, item.anomaly_score)
            for item in native.echoes
        ),
        forecast_bands=tuple(
            ForecastBand(
                item.horizon,
                item.lower,
                item.center,
                item.upper,
                item.coverage,
                item.sample_count,
            )
            for item in native.forecast_bands
        ),
        integrity=audit,
    )


def run_sonar_tracker(
    observations: Iterable[Observation],
    decision_cutoff_ms: int,
    horizons: Sequence[int] = DEFAULT_HORIZONS,
    research_config: str | None = None,
    universe_id: str | None = None,
    survivorship_controlled: bool = False,
) -> SonarReport:
    provided = tuple(observations)
    config, canonical_config = resolve_research_config(research_config, horizons)
    parsed_horizons = _validate_horizons(config.sonar_horizons)
    audit = build_integrity_audit(
        provided,
        decision_cutoff_ms,
        {"analysis": "sonar_tracker", "research_config": canonical_config},
        minimum_points=max(config.minimum_points, max(parsed_horizons) + 5),
        universe_id=universe_id,
        survivorship_controlled=survivorship_controlled,
    )
    if not audit.valid:
        details = "; ".join(item.message for item in audit.issues)
        raise ValueError(f"Integrity audit failed: {details}")
    native = _core.compute_sonar_with_config(
        as_native_bars(eligible_observations(provided, decision_cutoff_ms)),
        decision_cutoff_ms,
        config,
    )
    report = _sonar_report(native, decision_cutoff_ms, audit)
    return replace(
        report,
        manifest=create_run_manifest(
            {"analysis": "sonar_tracker", "research_config": canonical_config},
            {"observations": provided},
            report,
            decision_cutoff_ms,
            warnings=report.integrity.warnings,
        ),
    )


def _split_reference_evaluation(
    observations: tuple[Observation, ...],
    reference_size: int | None,
    minimum_reference: int,
    minimum_evaluation: int,
) -> tuple[tuple[Observation, ...], tuple[Observation, ...]]:
    if len(observations) < minimum_reference + minimum_evaluation:
        raise ValueError(
            "Regime analysis has insufficient eligible observations for the configured reference and evaluation windows"
        )
    split = (
        reference_size
        if reference_size is not None
        else max(minimum_reference, len(observations) * 2 // 3)
    )
    if split < minimum_reference or len(observations) - split < minimum_evaluation:
        raise ValueError(
            "reference_size must preserve the configured reference and evaluation minimums"
        )
    return observations[:split], observations[split:]


def analyze_regime_risk(
    observations: Iterable[Observation],
    decision_cutoff_ms: int,
    horizons: Sequence[int] = DEFAULT_HORIZONS,
    research_config: str | None = None,
    reference_size: int | None = None,
    universe_id: str | None = None,
    survivorship_controlled: bool = False,
) -> RegimeRiskReport:
    provided = tuple(observations)
    config, canonical_config = resolve_research_config(research_config, horizons)
    parsed_horizons = _validate_horizons(config.sonar_horizons)
    minimum_points = max(config.minimum_points, max(parsed_horizons) + 5)
    evaluation_minimum = max(config.evaluation_minimum_points, max(parsed_horizons) + 2)
    preflight_audit = build_integrity_audit(
        provided,
        decision_cutoff_ms,
        {
            "analysis": "regime_risk",
            "research_config": canonical_config,
            "reference_size": reference_size,
        },
        minimum_points=minimum_points,
        universe_id=universe_id,
        survivorship_controlled=survivorship_controlled,
    )
    if not preflight_audit.valid:
        details = "; ".join(item.message for item in preflight_audit.issues)
        raise ValueError(f"Integrity audit failed: {details}")
    eligible = eligible_observations(provided, decision_cutoff_ms)
    reference, evaluation = _split_reference_evaluation(
        eligible, reference_size, config.reference_minimum_points, evaluation_minimum
    )
    audit = build_integrity_audit(
        provided,
        decision_cutoff_ms,
        {
            "analysis": "regime_risk",
            "research_config": canonical_config,
            "reference_size": len(reference),
            "evaluation_size": len(evaluation),
        },
        minimum_points=minimum_points,
        universe_id=universe_id,
        survivorship_controlled=survivorship_controlled,
    )
    native = _core.classify_regime_with_config(
        as_native_bars(reference),
        as_native_bars(evaluation),
        decision_cutoff_ms,
        config,
    )
    sonar = _sonar_report(native.sonar, decision_cutoff_ms, audit)
    calibration = DistanceCalibrationReport(
        return_distance=native.calibration.return_distance,
        volatility_distance=native.calibration.volatility_distance,
        liquidity_distance=native.calibration.liquidity_distance,
        correlation_distance=native.calibration.correlation_distance,
        nearest_regime_distance=native.calibration.nearest_regime_distance,
        regime_risk_uncertainty=native.calibration.regime_risk_uncertainty,
        calibration_drift=native.calibration.calibration_drift,
        confidence=native.calibration.confidence,
    )
    report = RegimeRiskReport(
        decision_cutoff_ms=decision_cutoff_ms,
        regime=native.regime,
        regime_score=native.regime_score,
        confidence=native.confidence,
        uncertainty=native.uncertainty,
        calibration_drift=native.calibration_drift,
        sonar=sonar,
        calibration=calibration,
        integrity=audit,
    )
    return replace(
        report,
        manifest=create_run_manifest(
            {
                "analysis": "regime_risk",
                "research_config": canonical_config,
                "reference_size": len(reference),
            },
            {"observations": provided},
            report,
            decision_cutoff_ms,
            warnings=report.integrity.warnings,
        ),
    )
