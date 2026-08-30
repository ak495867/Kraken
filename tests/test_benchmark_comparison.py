import csv
import tempfile
import unittest
from pathlib import Path

from tools.compare_benchmarks import compare_results, read_results

POLICY = {
    "require_matching_compiler": True,
    "defaults": {
        "max_p50_regression_percent": 25.0,
        "max_p95_regression_percent": 25.0,
        "max_input_bar_copy_count": 0,
        "max_input_bar_copy_bytes": 0,
    },
    "workloads": {},
}


class BenchmarkComparisonTests(unittest.TestCase):
    def write_csv(
        self,
        directory: str,
        name: str,
        p50_ms: float,
        p95_ms: float,
        compiler: str = "gcc-13.3.0",
        copy_count: int = 0,
    ) -> Path:
        path = Path(directory) / name
        fieldnames = [
            "benchmark",
            "observations",
            "iterations",
            "samples",
            "p50_ms",
            "p95_ms",
            "checksum",
            "compiler",
            "input_bar_copy_count",
            "input_bar_copy_bytes",
            "temporary_double_buffer_count",
            "temporary_double_buffer_bytes",
        ]
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerow(
                {
                    "benchmark": "sonar_large_history",
                    "observations": 200000,
                    "iterations": 3,
                    "samples": 9,
                    "p50_ms": p50_ms,
                    "p95_ms": p95_ms,
                    "checksum": 0.1,
                    "compiler": compiler,
                    "input_bar_copy_count": copy_count,
                    "input_bar_copy_bytes": copy_count * 48,
                    "temporary_double_buffer_count": 1,
                    "temporary_double_buffer_bytes": 1599992,
                }
            )
        return path

    def test_comparison_passes_within_percentile_thresholds(self):
        with tempfile.TemporaryDirectory() as directory:
            result = compare_results(
                read_results(self.write_csv(directory, "baseline.csv", 10.0, 12.0)),
                read_results(self.write_csv(directory, "candidate.csv", 12.0, 14.0)),
                POLICY,
            )
            self.assertTrue(result["passed"])

    def test_comparison_fails_for_percentile_compiler_or_copy_regressions(self):
        with tempfile.TemporaryDirectory() as directory:
            baseline = read_results(
                self.write_csv(directory, "baseline.csv", 10.0, 12.0)
            )
            slow = read_results(self.write_csv(directory, "slow.csv", 14.0, 17.0))
            other_compiler = read_results(
                self.write_csv(directory, "other.csv", 10.0, 12.0, "clang-18.1.0")
            )
            copied = read_results(
                self.write_csv(directory, "copied.csv", 10.0, 12.0, copy_count=1)
            )
            self.assertFalse(compare_results(baseline, slow, POLICY)["passed"])
            self.assertFalse(
                compare_results(baseline, other_compiler, POLICY)["passed"]
            )
            self.assertFalse(compare_results(baseline, copied, POLICY)["passed"])
