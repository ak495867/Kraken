import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from kraken.cli import main


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "illustrative_market_data.csv"
OPTIONS_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "illustrative_option_quotes.csv"
MANIFEST_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "illustrative_vendor_manifest.json"
SNAPSHOT_EQUITY_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "illustrative_snapshot_equity.csv"
SNAPSHOT_OPTIONS_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "illustrative_snapshot_options.csv"
MAPPING_FIXTURE = Path(__file__).resolve().parents[1] / "vendor_mappings" / "licensed_snapshot_v1.json"


class CliTests(unittest.TestCase):
    def test_integrity_audit_json_output(self):
        output = io.StringIO()
        with redirect_stdout(output):
            main(["integrity", "audit", "--input", str(FIXTURE), "--format", "json"])
        payload = json.loads(output.getvalue())
        self.assertTrue(payload["valid"])
        self.assertIn("configuration_fingerprint", payload)

    def test_terminal_output_discloses_research_boundary(self):
        output = io.StringIO()
        with redirect_stdout(output):
            main(["sonar", "track", "--input", str(FIXTURE), "--format", "terminal"])
        self.assertIn("Research-only. Not trading instructions.", output.getvalue())

    def test_dynamics_and_options_backtest_json_output(self):
        dynamics_output = io.StringIO()
        with redirect_stdout(dynamics_output):
            main(["dynamics", "assess", "--input", str(FIXTURE), "--format", "json"])
        dynamics = json.loads(dynamics_output.getvalue())
        self.assertIn("composite_dynamics_risk", dynamics)
        backtest_output = io.StringIO()
        with redirect_stdout(backtest_output):
            main([
                "backtest", "options",
                "--equity-input", str(FIXTURE),
                "--options-input", str(OPTIONS_FIXTURE),
                "--train-size", "24",
                "--validation-size", "14",
                "--holding-size", "8",
                "--embargo-size", "2",
                "--format", "json",
            ])
        backtest = json.loads(backtest_output.getvalue())
        self.assertGreaterEqual(len(backtest["windows"]), 1)

    def test_vendor_backtest_and_calibration_diagnostics_json_output(self):
        vendor_output = io.StringIO()
        with redirect_stdout(vendor_output):
            main([
                "backtest", "vendor",
                "--manifest", str(MANIFEST_FIXTURE),
                "--train-size", "24",
                "--validation-size", "14",
                "--holding-size", "8",
                "--embargo-size", "2",
                "--format", "json",
            ])
        with tempfile.TemporaryDirectory() as directory:
            report_path = Path(directory) / "vendor-report.json"
            report_path.write_text(vendor_output.getvalue(), encoding="utf-8")
            diagnostics_output = io.StringIO()
            with redirect_stdout(diagnostics_output):
                main([
                    "diagnostics", "summarize",
                    "--backtest-json", str(report_path),
                    "--group-by", "sector",
                    "--format", "json",
                ])
        diagnostics = json.loads(diagnostics_output.getvalue())
        self.assertEqual(diagnostics["groups"][0]["group_label"], "Illustrative Sector")

    def test_normalizer_and_time_sliced_diagnostics_json_output(self):
        with tempfile.TemporaryDirectory() as directory:
            normalizer_output = io.StringIO()
            with redirect_stdout(normalizer_output):
                main([
                    "vendor", "normalize",
                    "--mapping-file", str(MAPPING_FIXTURE),
                    "--equity-source", str(SNAPSHOT_EQUITY_FIXTURE),
                    "--options-source", str(SNAPSHOT_OPTIONS_FIXTURE),
                    "--output-directory", directory,
                    "--format", "json",
                ])
            normalized = json.loads(normalizer_output.getvalue())
            self.assertGreater(normalized["equity_row_count"], 0)
        vendor_output = io.StringIO()
        with redirect_stdout(vendor_output):
            main([
                "backtest", "vendor",
                "--manifest", str(MANIFEST_FIXTURE),
                "--train-size", "24",
                "--validation-size", "14",
                "--holding-size", "8",
                "--embargo-size", "2",
                "--format", "json",
            ])
        with tempfile.TemporaryDirectory() as directory:
            report_path = Path(directory) / "vendor-report.json"
            report_path.write_text(vendor_output.getvalue(), encoding="utf-8")
            slice_output = io.StringIO()
            with redirect_stdout(slice_output):
                main([
                    "diagnostics", "timeslice",
                    "--backtest-json", str(report_path),
                    "--slice-size", "3",
                    "--format", "json",
                ])
        sliced = json.loads(slice_output.getvalue())
        self.assertGreaterEqual(len(sliced["slices"]), 2)

    def test_time_slice_visualization_json_output(self):
        vendor_output = io.StringIO()
        with redirect_stdout(vendor_output):
            main([
                "backtest", "vendor",
                "--manifest", str(MANIFEST_FIXTURE),
                "--train-size", "24",
                "--validation-size", "14",
                "--holding-size", "8",
                "--embargo-size", "2",
                "--format", "json",
            ])
        with tempfile.TemporaryDirectory() as directory:
            report_path = Path(directory) / "vendor-report.json"
            image_path = Path(directory) / "timeslice.png"
            report_path.write_text(vendor_output.getvalue(), encoding="utf-8")
            render_output = io.StringIO()
            with redirect_stdout(render_output):
                main([
                    "diagnostics", "visualize",
                    "--backtest-json", str(report_path),
                    "--slice-size", "3",
                    "--output", str(image_path),
                    "--format", "json",
                ])
            visualization = json.loads(render_output.getvalue())
            self.assertEqual(visualization["output_path"], str(image_path.resolve()))
            self.assertTrue(image_path.is_file())


if __name__ == "__main__":
    unittest.main()
