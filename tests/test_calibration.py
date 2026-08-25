import unittest
from dataclasses import replace
from pathlib import Path

from kraken import calibrate_forecast_bands, load_observations


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "illustrative_market_data.csv"


class ForecastCalibrationTests(unittest.TestCase):
    def test_empirical_calibration_reports_supported_coverage(self):
        report = calibrate_forecast_bands(load_observations(FIXTURE), horizons=(1, 5), step=5)
        self.assertGreater(report.decision_count, 0)
        self.assertEqual([metric.horizon for metric in report.metrics], [1, 5])
        for metric in report.metrics:
            self.assertGreater(metric.observation_count, 0)
            self.assertGreaterEqual(metric.empirical_coverage, 0.0)
            self.assertLessEqual(metric.empirical_coverage, 1.0)
            self.assertGreater(metric.mean_interval_width, 0.0)

    def test_empirical_calibration_rejects_non_chronological_inputs(self):
        observations = list(load_observations(FIXTURE))
        observations[3] = replace(observations[3], timestamp_ms=observations[2].timestamp_ms)
        with self.assertRaisesRegex(ValueError, "strictly chronological"):
            calibrate_forecast_bands(observations, horizons=(1,))

    def test_empirical_calibration_rejects_insufficient_outcomes(self):
        observations = load_observations(FIXTURE)[:24]
        with self.assertRaisesRegex(ValueError, "enough history"):
            calibrate_forecast_bands(observations, horizons=(10,))


if __name__ == "__main__":
    unittest.main()
