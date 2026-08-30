import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from kraken import load_observations, load_option_quotes, run_equity_options_backtest
from kraken.bundles import create_research_bundle

ROOT = Path(__file__).resolve().parents[1]


class ResearchBundleTests(unittest.TestCase):
    def setUp(self):
        self.report = run_equity_options_backtest(
            load_observations(ROOT / "fixtures" / "illustrative_market_data.csv"),
            load_option_quotes(ROOT / "fixtures" / "illustrative_option_quotes.csv"),
            train_size=24,
            validation_size=14,
            holding_size=8,
            embargo_size=2,
        )

    def test_bundle_writes_auditable_local_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "bundle"
            bundle = create_research_bundle(
                self.report,
                output,
                "\n".join(
                    (
                        "schema_version=2",
                        "sonar_horizons=1,5,10",
                        "minimum_points=4",
                        "reference_minimum_points=6",
                        "evaluation_minimum_points=4",
                        "reference_liquidity=0",
                        "drag_scale=1",
                        "fast_window=5",
                        "slow_window=20",
                        "calibration_decay=0.25",
                        "forecast_coverage=0.9",
                    )
                ),
            )
            self.assertEqual(len(bundle.bundle_sha256), 64)
            self.assertIn("report.json", bundle.files)
            self.assertIn("run_manifest.json", bundle.files)
            self.assertIn("integrity.json", bundle.files)
            self.assertIn("research_config.kcfg", bundle.files)
            self.assertIn("RESEARCH_ONLY_DISCLOSURE.md", bundle.files)
            manifest = json.loads(
                (output / "bundle_manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["run_id"], self.report.manifest.run_id)
            self.assertEqual(
                manifest["run_manifest_sha256"],
                hashlib.sha256((output / "run_manifest.json").read_bytes()).hexdigest(),
            )
            self.assertIn(
                "does not provide investment advice",
                (output / "RESEARCH_ONLY_DISCLOSURE.md").read_text(encoding="utf-8"),
            )

    def test_bundle_rejects_incomplete_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "bundle"
            with self.assertRaisesRegex(ValueError, "missing required key"):
                create_research_bundle(self.report, output, "schema_version=2\n")

    def test_bundle_rejects_nonempty_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "bundle"
            output.mkdir()
            (output / "existing.txt").write_text("existing", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must be empty"):
                create_research_bundle(self.report, output, "schema_version=2\n")


if __name__ == "__main__":
    unittest.main()
