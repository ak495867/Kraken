from __future__ import annotations

import math
from typing import Iterable, Sequence

from .analysis import DEFAULT_HORIZONS, run_sonar_tracker
from .models import ForecastCalibrationMetric, ForecastCalibrationReport, Observation


def calibrate_forecast_bands(
    observations: Iterable[Observation],
    horizons: Sequence[int] = DEFAULT_HORIZONS,
    research_config: str | None = None,
    step: int = 1,
    max_decisions: int | None = None,
) -> ForecastCalibrationReport:
    series = tuple(observations)
    parsed_horizons = tuple(sorted({int(horizon) for horizon in horizons}))
    if not parsed_horizons or any(horizon <= 0 for horizon in parsed_horizons):
        raise ValueError("Calibration horizons must contain positive integers")
    if step <= 0:
        raise ValueError("Calibration step must be positive")
    if max_decisions is not None and max_decisions <= 0:
        raise ValueError("Calibration max_decisions must be positive")
    if any(
        series[index].timestamp_ms <= series[index - 1].timestamp_ms
        for index in range(1, len(series))
    ):
        raise ValueError("Calibration observations must be strictly chronological")
    minimum_history = max(max(parsed_horizons) + 5, 20)
    first_decision = minimum_history - 1
    last_decision = len(series) - max(parsed_horizons) - 1
    if last_decision < first_decision:
        raise ValueError("Calibration requires enough history and post-cutoff outcomes")
    decisions = list(range(first_decision, last_decision + 1, step))
    if max_decisions is not None:
        decisions = decisions[-max_decisions:]
    covered: dict[int, int] = {horizon: 0 for horizon in parsed_horizons}
    counts: dict[int, int] = {horizon: 0 for horizon in parsed_horizons}
    widths: dict[int, list[float]] = {horizon: [] for horizon in parsed_horizons}
    for decision_index in decisions:
        cutoff = series[decision_index].available_at_ms
        report = run_sonar_tracker(
            series[: decision_index + 1],
            cutoff,
            parsed_horizons,
            research_config=research_config,
        )
        bands = {band.horizon: band for band in report.forecast_bands}
        for horizon in parsed_horizons:
            target = series[decision_index + horizon]
            if target.timestamp_ms <= cutoff or target.available_at_ms <= cutoff:
                continue
            band = bands[horizon]
            realized = math.log(target.close / series[decision_index].close)
            counts[horizon] += 1
            widths[horizon].append(band.upper - band.lower)
            if band.lower <= realized <= band.upper:
                covered[horizon] += 1
    metrics = []
    for horizon in parsed_horizons:
        if counts[horizon] == 0:
            raise ValueError(
                f"Calibration produced no valid post-cutoff outcomes for horizon {horizon}"
            )
        metrics.append(
            ForecastCalibrationMetric(
                horizon=horizon,
                nominal_coverage=next(iter(bands.values())).coverage,
                empirical_coverage=covered[horizon] / counts[horizon],
                observation_count=counts[horizon],
                covered_observation_count=covered[horizon],
                mean_interval_width=sum(widths[horizon]) / counts[horizon],
            )
        )
    return ForecastCalibrationReport(
        decision_count=len(decisions), metrics=tuple(metrics)
    )
