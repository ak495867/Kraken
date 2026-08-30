import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from kraken import (
    calibration_diagnostics,
    load_backtest_report,
    load_corporate_actions,
    load_distributions,
    load_earnings_events,
    load_observations,
    load_option_adjustments,
    load_option_quotes,
    normalize_provider_exports,
    render_time_sliced_diagnostics,
    run_equity_options_backtest,
    run_vendor_equity_options_backtest,
    time_sliced_calibration_diagnostics,
)
from kraken.models import to_primitive

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


class VendorDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.equity = load_observations(FIXTURES / "illustrative_market_data.csv")
        self.options = load_option_quotes(FIXTURES / "illustrative_option_quotes.csv")
        self.actions = load_corporate_actions(
            FIXTURES / "illustrative_corporate_actions.csv"
        )
        self.adjustments = load_option_adjustments(
            FIXTURES / "illustrative_option_adjustments.csv"
        )
        self.distributions = load_distributions(
            FIXTURES / "illustrative_distributions.csv"
        )
        self.earnings = load_earnings_events(
            FIXTURES / "illustrative_earnings_events.csv"
        )

    def test_manifest_adapter_carries_labels_and_validates_split_adjustments(self):
        report = run_vendor_equity_options_backtest(
            str(FIXTURES / "illustrative_vendor_manifest.json"),
            train_size=24,
            validation_size=14,
            holding_size=8,
            embargo_size=2,
            underlying="ILLUS",
        )
        self.assertEqual(report.sector, "Illustrative Sector")
        self.assertEqual(report.underlying_universe, "Illustrative Universe")
        self.assertGreaterEqual(len(report.windows), 1)

    def test_mismatched_option_split_adjustment_is_rejected(self):
        invalid_actions = (replace(self.actions[0], factor=3.0),)
        with self.assertRaisesRegex(ValueError, "Option-contract split factors"):
            run_equity_options_backtest(
                self.equity,
                self.options,
                train_size=24,
                validation_size=14,
                holding_size=8,
                embargo_size=2,
                corporate_actions=invalid_actions,
                option_adjustments=self.adjustments,
                price_basis="split_adjusted",
            )

    def test_calibration_diagnostics_group_by_sector_and_reload_json(self):
        report = run_vendor_equity_options_backtest(
            str(FIXTURES / "illustrative_vendor_manifest.json"),
            train_size=24,
            validation_size=14,
            holding_size=8,
            embargo_size=2,
        )
        diagnostics = calibration_diagnostics((report,), group_by="sector")
        self.assertEqual(diagnostics.groups[0].group_label, "Illustrative Sector")
        self.assertGreater(diagnostics.groups[0].window_count, 0)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            path.write_text(json.dumps(to_primitive(report)), encoding="utf-8")
            reloaded = load_backtest_report(path)
            self.assertEqual(reloaded, report)

    def test_snapshot_v1_normalizer_creates_valid_canonical_exports(self):
        with tempfile.TemporaryDirectory() as directory:
            normalized = normalize_provider_exports(
                "snapshot_v1",
                FIXTURES / "illustrative_snapshot_equity.csv",
                FIXTURES / "illustrative_snapshot_options.csv",
                directory,
            )
            self.assertEqual(normalized.equity_row_count, len(self.equity))
            self.assertEqual(normalized.option_row_count, len(self.options))
            self.assertEqual(
                load_observations(normalized.equity_output_path), self.equity
            )
            self.assertEqual(
                load_option_quotes(normalized.options_output_path), self.options
            )

    def test_mapping_file_normalizer_creates_valid_canonical_exports(self):
        with tempfile.TemporaryDirectory() as directory:
            normalized = normalize_provider_exports(
                "mapping_file",
                FIXTURES / "illustrative_snapshot_equity.csv",
                FIXTURES / "illustrative_snapshot_options.csv",
                directory,
                mapping_file=FIXTURES.parent
                / "vendor_mappings"
                / "licensed_snapshot_v1.json",
            )
            self.assertEqual(normalized.provider_profile, "licensed_snapshot_v1")
            self.assertEqual(
                load_observations(normalized.equity_output_path), self.equity
            )

    def test_unavailable_earnings_event_is_rejected_during_backtest(self):
        leaky_earnings = (
            replace(
                self.earnings[0],
                available_at_ms=self.equity[-1].available_at_ms + 86_400_000,
            ),
            self.earnings[1],
        )
        with self.assertRaisesRegex(ValueError, "Earnings event was not available"):
            run_equity_options_backtest(
                self.equity,
                self.options,
                train_size=24,
                validation_size=14,
                holding_size=8,
                embargo_size=2,
                corporate_actions=self.actions,
                option_adjustments=self.adjustments,
                distributions=self.distributions,
                earnings_events=leaky_earnings,
                price_basis="split_adjusted",
            )

    def test_unavailable_distribution_is_rejected_during_backtest(self):
        leaky_distributions = (
            replace(
                self.distributions[0],
                available_at_ms=self.equity[-1].available_at_ms + 86_400_000,
            ),
            self.distributions[1],
        )
        with self.assertRaisesRegex(
            ValueError, "Cash dividend or special distribution was not available"
        ):
            run_equity_options_backtest(
                self.equity,
                self.options,
                train_size=24,
                validation_size=14,
                holding_size=8,
                embargo_size=2,
                corporate_actions=self.actions,
                option_adjustments=self.adjustments,
                distributions=leaky_distributions,
                price_basis="split_adjusted",
            )

    def test_time_sliced_diagnostics_are_chronological(self):
        report = run_vendor_equity_options_backtest(
            str(FIXTURES / "illustrative_vendor_manifest.json"),
            train_size=24,
            validation_size=14,
            holding_size=8,
            embargo_size=2,
        )
        diagnostics = time_sliced_calibration_diagnostics((report,), slice_size=3)
        self.assertGreaterEqual(len(diagnostics.slices), 2)
        self.assertLess(
            diagnostics.slices[0].end_cutoff_ms, diagnostics.slices[1].start_cutoff_ms
        )
        self.assertIsNone(diagnostics.slices[0].composite_risk_change_from_prior_slice)
        self.assertIsNotNone(
            diagnostics.slices[1].composite_risk_change_from_prior_slice
        )
        with tempfile.TemporaryDirectory() as directory:
            visualization = render_time_sliced_diagnostics(
                diagnostics, Path(directory) / "timeslice.png"
            )
            image = Path(visualization.output_path)
            self.assertTrue(image.is_file())
            self.assertGreater(image.stat().st_size, 10_000)


if __name__ == "__main__":
    unittest.main()
