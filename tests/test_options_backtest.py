import unittest
from dataclasses import replace
from pathlib import Path

from kraken import load_observations, load_option_quotes, run_equity_options_backtest

EQUITY_FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "illustrative_market_data.csv"
)
OPTIONS_FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "illustrative_option_quotes.csv"
)


class EquityOptionsBacktestTests(unittest.TestCase):
    def setUp(self):
        self.equity = load_observations(EQUITY_FIXTURE)
        self.options = load_option_quotes(OPTIONS_FIXTURE)

    def test_backtest_is_chronological_and_research_only(self):
        report = run_equity_options_backtest(
            self.equity,
            self.options,
            train_size=24,
            validation_size=14,
            holding_size=8,
            embargo_size=2,
            universe_id="illustrative-equity-options",
        )
        self.assertGreaterEqual(len(report.windows), 1)
        self.assertIn(
            "does not model orders, positions, or P&L", " ".join(report.warnings)
        )
        for window in report.windows:
            self.assertLess(window.decision_cutoff_ms, window.evaluation_start_ms)
            self.assertLessEqual(window.quote_timestamp_ms, window.decision_cutoff_ms)
            self.assertTrue(window.integrity.valid)
            self.assertGreaterEqual(window.absolute_move_ratio, 0.0)

    def test_backtest_rejects_later_evaluation_record_before_cutoff(self):
        leaky_equity = list(self.equity[:50])
        leaky_equity[49] = replace(
            leaky_equity[49], timestamp_ms=leaky_equity[39].timestamp_ms
        )
        with self.assertRaisesRegex(ValueError, "remain strictly after"):
            run_equity_options_backtest(
                leaky_equity, self.options, 24, 14, 8, embargo_size=2
            )

    def test_backtest_rejects_option_availability_leakage(self):
        leaky = list(self.options)
        leaky[0] = replace(
            leaky[0], available_at_ms=self.options[-1].available_at_ms + 86_400_000
        )
        with self.assertRaisesRegex(ValueError, "unavailable at the decision cutoff"):
            run_equity_options_backtest(self.equity, leaky, 24, 14, 8, embargo_size=2)


if __name__ == "__main__":
    unittest.main()
