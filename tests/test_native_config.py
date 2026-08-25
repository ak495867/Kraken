import unittest

from kraken import _core


class NativeConfigTests(unittest.TestCase):
    def make_bars(self, count=30):
        values = []
        for index in range(count):
            bar = _core.Bar()
            bar.timestamp_ms = 1_700_000_000_000 + index * 86_400_000
            bar.available_at_ms = bar.timestamp_ms
            bar.close = 100.0 + index * 0.7 + (index % 4) * 0.2
            bar.volume = 1_000_000.0 + index * 12_000.0
            bar.realized_volatility = 0.18 + (index % 5) * 0.01
            bar.liquidity = 800_000.0 + index * 9_000.0
            values.append(bar)
        return values

    def test_versioned_native_configuration_roundtrips(self):
        config = _core.default_research_config()
        document = _core.serialize_research_config(config)
        parsed = _core.parse_research_config(document)
        self.assertEqual(parsed.schema_version, 2)
        self.assertEqual(list(parsed.sonar_horizons), [1, 5, 10])
        _core.validate_research_config(parsed)

    def test_schema_v1_configuration_migrates_to_v2(self):
        document = "\n".join([
            "schema_version=1",
            "sonar_horizons=1,5,10",
            "minimum_points=4",
            "reference_minimum_points=6",
            "evaluation_minimum_points=4",
            "reference_liquidity=0",
            "drag_scale=1",
            "fast_window=5",
            "slow_window=20",
        ])
        migrated = _core.parse_research_config(document)
        self.assertEqual(migrated.schema_version, 2)
        self.assertEqual(migrated.calibration_decay, 0.25)
        self.assertEqual(migrated.forecast_coverage, 0.9)

    def test_unsupported_native_configuration_schema_is_rejected(self):
        document = "\n".join([
            "schema_version=3",
            "sonar_horizons=1,5,10",
            "minimum_points=4",
            "reference_minimum_points=6",
            "evaluation_minimum_points=4",
            "reference_liquidity=0",
            "drag_scale=1",
            "fast_window=5",
            "slow_window=20",
        ])
        with self.assertRaises(ValueError):
            _core.parse_research_config(document)

    def test_config_drives_native_sonar_regime_and_dynamics(self):
        bars = self.make_bars()
        cutoff = bars[-1].timestamp_ms
        default = _core.default_research_config()
        configured = _core.default_research_config()
        configured.forecast_coverage = 0.8
        configured.calibration_decay = 0.9
        configured.drag_scale = 3.0
        default_sonar = _core.compute_sonar_with_config(bars, cutoff, default)
        configured_sonar = _core.compute_sonar_with_config(bars, cutoff, configured)
        default_regime = _core.classify_regime_with_config(bars[:12], bars[12:], cutoff, default)
        configured_regime = _core.classify_regime_with_config(bars[:12], bars[12:], cutoff, configured)
        default_dynamics = _core.compute_marine_dynamics_with_config(bars, cutoff, default)
        configured_dynamics = _core.compute_marine_dynamics_with_config(bars, cutoff, configured)
        self.assertEqual(default_sonar.forecast_bands[0].coverage, 0.9)
        self.assertEqual(configured_sonar.forecast_bands[0].coverage, 0.8)
        self.assertEqual(default_sonar.forecast_bands[0].sample_count, len(bars) - default_sonar.forecast_bands[0].horizon)
        self.assertLessEqual(default_sonar.forecast_bands[0].lower, default_sonar.forecast_bands[0].center)
        self.assertLessEqual(default_sonar.forecast_bands[0].center, default_sonar.forecast_bands[0].upper)
        self.assertLessEqual(configured_sonar.forecast_bands[0].upper - configured_sonar.forecast_bands[0].lower, default_sonar.forecast_bands[0].upper - default_sonar.forecast_bands[0].lower)
        self.assertLessEqual(configured_regime.confidence, default_regime.confidence)
        self.assertGreater(configured_dynamics.drag.adjusted_volatility, default_dynamics.drag.adjusted_volatility)


if __name__ == "__main__":
    unittest.main()
