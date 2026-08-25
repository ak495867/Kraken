import unittest
from dataclasses import replace
from pathlib import Path

from kraken import load_observations, run_walk_forward


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "illustrative_market_data.csv"


class WalkForwardTests(unittest.TestCase):
    def test_windows_respect_embargo_and_chronology(self):
        observations = load_observations(FIXTURE)
        report = run_walk_forward(
            observations,
            train_size=24,
            validation_size=14,
            test_size=8,
            embargo_size=2,
            horizons=(1, 5, 10),
            universe_id="illustrative-fixture",
            survivorship_controlled=False,
        )
        self.assertGreaterEqual(len(report.windows), 1)
        self.assertIsNotNone(report.manifest)
        self.assertEqual(report.manifest.decision_cutoff_ms, report.windows[-1].decision_cutoff_ms)
        for window in report.windows:
            self.assertLess(window.train_end_ms, window.validation_start_ms)
            self.assertLess(window.validation_end_ms, window.evaluation_start_ms)
            self.assertLess(window.decision_cutoff_ms, window.evaluation_start_ms)
            self.assertTrue(window.integrity.valid)
            self.assertIn("Survivorship control was not declared", " ".join(window.integrity.warnings))

    def test_insufficient_history_is_rejected(self):
        observations = load_observations(FIXTURE)[:20]
        with self.assertRaises(ValueError):
            run_walk_forward(observations, 10, 6, 4, embargo_size=1)

    def test_walk_forward_rejects_unavailable_history(self):
        observations = list(load_observations(FIXTURE))
        observations[5] = replace(observations[5], available_at_ms=observations[-1].available_at_ms + 86_400_000)
        with self.assertRaisesRegex(ValueError, "unavailable at the decision cutoff"):
            run_walk_forward(observations, 24, 14, 8, embargo_size=2, horizons=(1, 5, 10))

    def test_walk_forward_rejects_later_evaluation_record_before_cutoff(self):
        observations = list(load_observations(FIXTURE)[:50])
        observations[49] = replace(observations[49], timestamp_ms=observations[39].timestamp_ms)
        with self.assertRaisesRegex(ValueError, "remain strictly after"):
            run_walk_forward(observations, 24, 14, 8, embargo_size=2, horizons=(1, 5, 10))

    def test_walk_forward_rejects_future_timestamp_in_history(self):
        observations = list(load_observations(FIXTURE))
        observations[5] = replace(
            observations[5],
            timestamp_ms=observations[42].timestamp_ms,
            available_at_ms=observations[42].available_at_ms,
        )
        with self.assertRaisesRegex(ValueError, "after the decision cutoff"):
            run_walk_forward(observations, 24, 14, 8, embargo_size=2, horizons=(1, 5, 10))


if __name__ == "__main__":
    unittest.main()
