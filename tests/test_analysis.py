import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from kraken import analyze_regime_risk, load_observations, run_sonar_tracker
from kraken.audit import build_integrity_audit

FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "illustrative_market_data.csv"
)


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.observations = load_observations(FIXTURE)
        self.cutoff = self.observations[-1].available_at_ms

    def test_sonar_is_deterministic_and_structured(self):
        first = run_sonar_tracker(self.observations, self.cutoff, horizons=(1, 5, 10))
        second = run_sonar_tracker(self.observations, self.cutoff, horizons=(1, 5, 10))
        self.assertEqual(first, second)
        self.assertEqual(tuple(item.horizon for item in first.echoes), (1, 5, 10))
        self.assertGreaterEqual(first.signal_strength, 0.0)
        self.assertTrue(first.integrity.valid)

    def test_regime_report_exposes_all_risk_fields(self):
        report = analyze_regime_risk(
            self.observations, self.cutoff, horizons=(1, 5, 10), reference_size=64
        )
        self.assertIn(
            report.regime, {"stable", "transitional", "stressed", "dislocated"}
        )
        self.assertGreaterEqual(report.confidence, 0.0)
        self.assertLessEqual(report.confidence, 1.0)
        self.assertGreaterEqual(report.uncertainty, 0.0)
        self.assertLessEqual(report.uncertainty, 1.0)
        self.assertGreaterEqual(report.calibration.calibration_drift, 0.0)

    def test_future_records_are_rejected_and_flagged(self):
        cutoff = self.observations[-2].available_at_ms
        audit = build_integrity_audit(
            self.observations,
            cutoff,
            {"analysis": "test"},
            minimum_points=4,
        )
        self.assertFalse(audit.valid)
        self.assertEqual(audit.excluded_future_timestamp_count, 1)
        self.assertIn("future_timestamp_access_prevented", audit.leakage_flags)
        self.assertEqual(audit.issues[0].code, "future_timestamp")
        with self.assertRaisesRegex(ValueError, "after the decision cutoff"):
            run_sonar_tracker(self.observations, cutoff, horizons=(1, 5, 10))

    def test_unavailable_record_is_rejected_and_flagged(self):
        last = self.observations[-1]
        leaky = self.observations[:-1] + (
            replace(last, available_at_ms=last.available_at_ms + 86_400_000),
        )
        audit = build_integrity_audit(
            leaky, self.cutoff, {"analysis": "test"}, minimum_points=4
        )
        self.assertFalse(audit.valid)
        self.assertEqual(audit.excluded_unavailable_count, 1)
        self.assertIn("availability_timestamp_access_prevented", audit.leakage_flags)
        self.assertEqual(audit.issues[0].code, "availability_leakage")
        with self.assertRaisesRegex(ValueError, "unavailable at the decision cutoff"):
            run_sonar_tracker(leaky, self.cutoff, horizons=(1, 5, 10))

    def test_regime_analysis_rejects_future_and_unavailable_records(self):
        earlier_cutoff = self.observations[-2].available_at_ms
        with self.assertRaisesRegex(ValueError, "after the decision cutoff"):
            analyze_regime_risk(self.observations, earlier_cutoff, horizons=(1, 5, 10))
        last = self.observations[-1]
        leaky = self.observations[:-1] + (
            replace(last, available_at_ms=last.available_at_ms + 86_400_000),
        )
        with self.assertRaisesRegex(ValueError, "unavailable at the decision cutoff"):
            analyze_regime_risk(leaky, self.cutoff, horizons=(1, 5, 10))

    def test_invalid_availability_is_rejected_during_parse(self):
        payload = "timestamp,available_at,close,volume,realized_volatility,liquidity\n2025-01-02T00:00:00Z,2025-01-01T00:00:00Z,100,1000,0.01,2000\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.csv"
            path.write_text(payload, encoding="utf-8")
            with self.assertRaises(ValueError):
                load_observations(path)


if __name__ == "__main__":
    unittest.main()
