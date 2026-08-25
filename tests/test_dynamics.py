import unittest
from dataclasses import replace
from pathlib import Path

from kraken import analyze_marine_dynamics, load_observations


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "illustrative_market_data.csv"


class DynamicsTests(unittest.TestCase):
    def setUp(self):
        self.observations = load_observations(FIXTURE)
        self.cutoff = self.observations[-1].available_at_ms

    def test_marine_dynamics_is_deterministic_and_bounded(self):
        first = analyze_marine_dynamics(self.observations, self.cutoff, fast_window=5, slow_window=20)
        second = analyze_marine_dynamics(self.observations, self.cutoff, fast_window=5, slow_window=20)
        self.assertEqual(first, second)
        self.assertGreaterEqual(first.drag.adjusted_volatility, 0.0)
        self.assertGreaterEqual(first.cavitation.cavitation_score, 0.0)
        self.assertLessEqual(first.cavitation.cavitation_score, 1.0)
        self.assertGreaterEqual(first.buoyancy.buoyancy_score, 0.0)
        self.assertLessEqual(first.buoyancy.buoyancy_score, 1.0)
        self.assertGreaterEqual(first.composite_dynamics_risk, 0.0)
        self.assertLessEqual(first.composite_dynamics_risk, 1.0)

    def test_marine_dynamics_rejects_unavailable_history(self):
        leaky = self.observations[:-1] + (replace(self.observations[-1], available_at_ms=self.cutoff + 86_400_000),)
        with self.assertRaisesRegex(ValueError, "unavailable at the decision cutoff"):
            analyze_marine_dynamics(leaky, self.cutoff, fast_window=5, slow_window=20)


if __name__ == "__main__":
    unittest.main()

