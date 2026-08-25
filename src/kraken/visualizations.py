from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as pyplot

from .audit import configuration_fingerprint
from .models import TimeSliceVisualizationReport, TimeSlicedCalibrationDiagnosticsReport


def render_time_sliced_diagnostics(
    report: TimeSlicedCalibrationDiagnosticsReport,
    output_path: str | Path,
) -> TimeSliceVisualizationReport:
    if not report.slices:
        raise ValueError("Time-sliced diagnostics must contain at least one slice to render")
    destination = Path(output_path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    positions = [slice_.slice_id for slice_ in report.slices]
    composite = [slice_.mean_composite_dynamics_risk for slice_ in report.slices]
    cavitation = [slice_.mean_cavitation_score for slice_ in report.slices]
    buoyancy = [slice_.mean_buoyancy_score for slice_ in report.slices]
    coverage = [slice_.implied_move_coverage_rate for slice_ in report.slices]
    move_ratio = [slice_.mean_absolute_move_ratio for slice_ in report.slices]
    tidal = [slice_.mean_tidal_current_strength for slice_ in report.slices]
    figure, axes = pyplot.subplots(2, 1, figsize=(12, 8), sharex=True, layout="constrained")
    figure.patch.set_facecolor("#071525")
    for axis in axes:
        axis.set_facecolor("#0d2135")
        axis.tick_params(colors="#c9d8e6")
        axis.spines["bottom"].set_color("#4c6377")
        axis.spines["left"].set_color("#4c6377")
        axis.spines["top"].set_visible(False)
        axis.spines["right"].set_visible(False)
        axis.grid(axis="y", color="#4c6377", alpha=0.35, linewidth=0.8)
    axes[0].plot(positions, composite, color="#34d1bf", linewidth=2.4, marker="o", label="Composite dynamics risk")
    axes[0].plot(positions, cavitation, color="#ff9f5a", linewidth=1.8, marker="o", label="Cavitation score")
    axes[0].plot(positions, buoyancy, color="#7bb6ff", linewidth=1.8, marker="o", label="Buoyancy score")
    axes[0].set_ylim(0.0, 1.0)
    axes[0].set_ylabel("Bounded score", color="#c9d8e6")
    axes[0].set_title("Kraken Marine Dynamics: Chronological Regime-Shift Slices", color="#f4fbff", loc="left", fontsize=14, fontweight="bold")
    axes[0].legend(frameon=False, labelcolor="#c9d8e6", loc="upper left", ncol=3)
    axes[1].plot(positions, coverage, color="#d4b3ff", linewidth=2.2, marker="o", label="Implied-move coverage")
    axes[1].plot(positions, tidal, color="#ffd166", linewidth=1.8, marker="o", label="Tidal current strength")
    axes[1].plot(positions, move_ratio, color="#f07c9c", linewidth=1.8, marker="o", label="Absolute move ratio")
    axes[1].set_ylabel("Diagnostic value", color="#c9d8e6")
    axes[1].set_xlabel("Chronological slice", color="#c9d8e6")
    axes[1].set_xticks(positions)
    axes[1].legend(frameon=False, labelcolor="#c9d8e6", loc="upper left", ncol=3)
    figure.savefig(destination, dpi=180, facecolor=figure.get_facecolor())
    pyplot.close(figure)
    return TimeSliceVisualizationReport(
        output_path=str(destination),
        slice_count=len(report.slices),
        configuration_fingerprint=configuration_fingerprint(
            {
                "slice_size": report.slice_size,
                "slice_count": len(report.slices),
                "output_path": str(destination),
            }
        ),
    )
