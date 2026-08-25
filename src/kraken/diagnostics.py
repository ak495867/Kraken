from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .models import CalibrationDiagnosticGroup, CalibrationDiagnosticsReport, CalibrationTimeSlice, EquityOptionsBacktestReport, TimeSlicedCalibrationDiagnosticsReport
from .provenance import verify_run_manifest


def calibration_diagnostics(
    reports: Iterable[EquityOptionsBacktestReport],
    group_by: str = "underlying_universe",
) -> CalibrationDiagnosticsReport:
    if group_by not in {"sector", "underlying_universe"}:
        raise ValueError("group_by must be sector or underlying_universe")
    grouped: dict[str, list] = {}
    for report in reports:
        label = report.sector if group_by == "sector" else report.underlying_universe
        normalized_label = label or "unclassified"
        grouped.setdefault(normalized_label, []).extend(report.windows)
    if not grouped:
        raise ValueError("At least one backtest report is required for calibration diagnostics")
    groups: list[CalibrationDiagnosticGroup] = []
    for label in sorted(grouped):
        windows = grouped[label]
        count = len(windows)
        groups.append(
            CalibrationDiagnosticGroup(
                group_label=label,
                window_count=count,
                implied_move_coverage_rate=sum(1 for window in windows if window.implied_move_covered) / count,
                mean_absolute_move_ratio=sum(window.absolute_move_ratio for window in windows) / count,
                mean_composite_dynamics_risk=sum(window.composite_dynamics_risk for window in windows) / count,
                mean_drag_adjusted_volatility=sum(window.drag_adjusted_volatility for window in windows) / count,
                mean_tidal_current_strength=sum(window.tidal_current_strength for window in windows) / count,
                mean_cavitation_score=sum(window.cavitation_score for window in windows) / count,
                mean_buoyancy_score=sum(window.buoyancy_score for window in windows) / count,
            )
        )
    return CalibrationDiagnosticsReport(
        group_by=group_by,
        groups=tuple(groups),
        warnings=(
            "Diagnostics summarize calibration and marine-dynamics research fields; they do not measure investable performance or produce trading instructions",
            "Groups depend on user-supplied sector and underlying-universe labels from licensed point-in-time manifests",
        ),
    )


def time_sliced_calibration_diagnostics(
    reports: Iterable[EquityOptionsBacktestReport],
    slice_size: int,
) -> TimeSlicedCalibrationDiagnosticsReport:
    if slice_size <= 0:
        raise ValueError("slice_size must be a positive integer")
    windows = sorted(
        (window for report in reports for window in report.windows),
        key=lambda window: (window.decision_cutoff_ms, window.window_id),
    )
    if not windows:
        raise ValueError("At least one backtest window is required for time-sliced diagnostics")
    slices: list[CalibrationTimeSlice] = []
    previous_risk: float | None = None
    for start in range(0, len(windows), slice_size):
        subset = windows[start : start + slice_size]
        count = len(subset)
        mean_risk = sum(window.composite_dynamics_risk for window in subset) / count
        slices.append(
            CalibrationTimeSlice(
                slice_id=len(slices) + 1,
                start_cutoff_ms=subset[0].decision_cutoff_ms,
                end_cutoff_ms=subset[-1].decision_cutoff_ms,
                window_count=count,
                implied_move_coverage_rate=sum(1 for window in subset if window.implied_move_covered) / count,
                mean_absolute_move_ratio=sum(window.absolute_move_ratio for window in subset) / count,
                mean_composite_dynamics_risk=mean_risk,
                mean_drag_adjusted_volatility=sum(window.drag_adjusted_volatility for window in subset) / count,
                mean_tidal_current_strength=sum(window.tidal_current_strength for window in subset) / count,
                mean_cavitation_score=sum(window.cavitation_score for window in subset) / count,
                mean_buoyancy_score=sum(window.buoyancy_score for window in subset) / count,
                composite_risk_change_from_prior_slice=None if previous_risk is None else mean_risk - previous_risk,
            )
        )
        previous_risk = mean_risk
    return TimeSlicedCalibrationDiagnosticsReport(
        slice_size=slice_size,
        slices=tuple(slices),
        warnings=(
            "Time slices are chronological summaries of available research windows and are not forecasts, trading signals, or performance claims",
            "Composite-risk changes compare adjacent diagnostic slices only; they do not establish causality or investability",
        ),
    )


def load_backtest_report(path: str | Path) -> EquityOptionsBacktestReport:
    source = Path(path).expanduser().resolve()
    with source.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    required = {"configuration_fingerprint", "train_size", "validation_size", "holding_size", "embargo_size", "sector", "underlying_universe", "windows", "warnings"}
    if not isinstance(payload, dict) or (set(payload) - {"manifest"}) != required:
        raise ValueError("Backtest diagnostics input must be a Kraken equity-options JSON report")
    from .models import EquityOptionsBacktestWindow, IntegrityAudit, IntegrityIssue, RunManifest
    windows = []
    for item in payload["windows"]:
        integrity_payload = item["integrity"]
        integrity = IntegrityAudit(
            valid=integrity_payload["valid"],
            decision_cutoff_ms=integrity_payload["decision_cutoff_ms"],
            provided_input_count=integrity_payload["provided_input_count"],
            eligible_input_count=integrity_payload["eligible_input_count"],
            excluded_future_timestamp_count=integrity_payload["excluded_future_timestamp_count"],
            excluded_unavailable_count=integrity_payload["excluded_unavailable_count"],
            feature_window_start_ms=integrity_payload["feature_window_start_ms"],
            feature_window_end_ms=integrity_payload["feature_window_end_ms"],
            rebalance_timing=integrity_payload["rebalance_timing"],
            universe_id=integrity_payload["universe_id"],
            survivorship_controlled=integrity_payload["survivorship_controlled"],
            chronology_check=integrity_payload["chronology_check"],
            leakage_flags=tuple(integrity_payload["leakage_flags"]),
            warnings=tuple(integrity_payload["warnings"]),
            issues=tuple(IntegrityIssue(**issue) for issue in integrity_payload["issues"]),
            configuration_fingerprint=integrity_payload["configuration_fingerprint"],
        )
        windows.append(EquityOptionsBacktestWindow(integrity=integrity, **{key: value for key, value in item.items() if key != "integrity"}))
    manifest_payload = payload.get("manifest")
    manifest = None
    if manifest_payload is not None:
        manifest_fields = {
            "run_id",
            "engine_version",
            "decision_cutoff_ms",
            "configuration_sha256",
            "input_sha256",
            "output_sha256",
            "vendor_manifest_sha256",
            "platform",
            "python_version",
            "compiler",
            "warnings",
        }
        if not isinstance(manifest_payload, dict) or set(manifest_payload) != manifest_fields:
            raise ValueError("Backtest report manifest fields do not match the immutable Kraken manifest schema")
        manifest = RunManifest(
            run_id=manifest_payload["run_id"],
            engine_version=manifest_payload["engine_version"],
            decision_cutoff_ms=manifest_payload["decision_cutoff_ms"],
            configuration_sha256=manifest_payload["configuration_sha256"],
            input_sha256=tuple((str(item[0]), str(item[1])) for item in manifest_payload["input_sha256"]),
            output_sha256=manifest_payload["output_sha256"],
            vendor_manifest_sha256=manifest_payload["vendor_manifest_sha256"],
            platform=manifest_payload["platform"],
            python_version=manifest_payload["python_version"],
            compiler=manifest_payload["compiler"],
            warnings=tuple(manifest_payload["warnings"]),
        )
    report = EquityOptionsBacktestReport(
        configuration_fingerprint=payload["configuration_fingerprint"],
        train_size=payload["train_size"],
        validation_size=payload["validation_size"],
        holding_size=payload["holding_size"],
        embargo_size=payload["embargo_size"],
        sector=payload["sector"],
        underlying_universe=payload["underlying_universe"],
        windows=tuple(windows),
        warnings=tuple(payload["warnings"]),
        manifest=manifest,
    )
    if manifest is not None:
        verify_run_manifest(manifest, report)
    return report
