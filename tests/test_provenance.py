import unittest

import json
import tempfile
from pathlib import Path

from kraken.analysis import run_sonar_tracker
from kraken.backtest import run_equity_options_backtest
from kraken.diagnostics import load_backtest_report
from kraken.dynamics import analyze_marine_dynamics
from kraken.io import load_observations, load_option_quotes
from kraken.models import to_primitive
from kraken.provenance import compare_run_manifests, load_run_manifest


class ProvenanceTests(unittest.TestCase):
    def test_manifests_are_immutable_and_deterministic(self):
        observations = load_observations("fixtures/illustrative_market_data.csv")
        cutoff = observations[-1].timestamp_ms
        first = run_sonar_tracker(observations, cutoff)
        second = run_sonar_tracker(observations, cutoff)
        self.assertIsNotNone(first.manifest)
        self.assertEqual(first.manifest.run_id, second.manifest.run_id)
        comparison = compare_run_manifests(first.manifest, second.manifest)
        self.assertFalse(comparison.output_changed)
        self.assertEqual(comparison.summary, ("Manifests are identical",))

    def test_manifest_comparison_explains_config_driven_output_change(self):
        observations = load_observations("fixtures/illustrative_market_data.csv")
        cutoff = observations[-1].timestamp_ms
        default = analyze_marine_dynamics(observations, cutoff)
        configured = analyze_marine_dynamics(observations, cutoff, drag_scale=2.0)
        comparison = compare_run_manifests(default.manifest, configured.manifest)
        self.assertTrue(comparison.configuration_changed)
        self.assertTrue(comparison.output_changed)

    def test_tampered_saved_backtest_report_is_rejected(self):
        report = run_equity_options_backtest(
            load_observations("fixtures/illustrative_market_data.csv"),
            load_option_quotes("fixtures/illustrative_option_quotes.csv"),
            train_size=24,
            validation_size=14,
            holding_size=8,
            embargo_size=2,
        )
        payload = to_primitive(report)
        payload["windows"][0]["realized_log_return"] += 1.0
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "output hash"):
                load_backtest_report(path)

    def test_standalone_manifest_roundtrip_is_comparable(self):
        observations = load_observations("fixtures/illustrative_market_data.csv")
        report = run_sonar_tracker(observations, observations[-1].timestamp_ms)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(json.dumps(to_primitive(report.manifest), sort_keys=True), encoding="utf-8")
            loaded = load_run_manifest(path)
            comparison = compare_run_manifests(report.manifest, loaded)
            self.assertEqual(loaded, report.manifest)
            self.assertEqual(comparison.summary, ("Manifests are identical",))
