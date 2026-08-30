from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import unittest

from kraken import load_observations, load_option_quotes, run_equity_options_backtest
from kraken.calendar import validate_market_data_quality
from kraken.models import ExchangeSession, MarketDataQualityPolicy

EQUITY_FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "illustrative_market_data.csv"
)
OPTIONS_FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "illustrative_option_quotes.csv"
)


def _sessions(observations):
    return tuple(
        ExchangeSession(
            session_date=datetime.fromtimestamp(
                item.timestamp_ms / 1000, tz=timezone.utc
            )
            .date()
            .isoformat(),
            open_ms=item.timestamp_ms,
            close_ms=item.timestamp_ms + 86_399_999,
            is_half_day=False,
        )
        for item in observations
    )


class CalendarQualityTests(unittest.TestCase):
    def setUp(self):
        self.equity = load_observations(EQUITY_FIXTURE)
        self.options = load_option_quotes(OPTIONS_FIXTURE)
        self.sessions = _sessions(self.equity)
        self.cutoff = self.equity[37].available_at_ms

    def test_explicit_calendar_accepts_complete_local_history(self):
        report = validate_market_data_quality(
            self.equity[:38], self.options, self.cutoff, self.sessions
        )
        self.assertTrue(report.valid)
        self.assertEqual(report.duplicate_snapshot_count, 0)
        self.assertEqual(report.stale_snapshot_count, 0)
        self.assertEqual(report.incomplete_option_chain_count, 0)

    def test_quality_report_detects_duplicate_stale_and_incomplete_snapshots(self):
        stale = replace(
            self.equity[0], available_at_ms=self.equity[0].timestamp_ms + 600_000
        )
        calls_only = tuple(item for item in self.options if item.option_type == "call")
        report = validate_market_data_quality(
            (stale, stale),
            calls_only,
            self.cutoff,
            self.sessions,
            MarketDataQualityPolicy(strict=False),
            halted_underlyings=("ILLUS",),
        )
        codes = {item.code for item in report.issues}
        self.assertTrue(report.valid)
        self.assertGreater(report.duplicate_snapshot_count, 0)
        self.assertGreater(report.stale_snapshot_count, 0)
        self.assertGreater(report.incomplete_option_chain_count, 0)
        self.assertTrue(
            {
                "duplicate_observation_snapshot",
                "stale_observation_snapshot",
                "incomplete_option_chain",
                "halted_underlying_quote",
            }.issubset(codes)
        )

    def test_backtest_rejects_incomplete_option_chain_under_strict_policy(self):
        calls_only = tuple(item for item in self.options if item.option_type == "call")
        with self.assertRaisesRegex(
            ValueError, "Calendar and market-data quality validation failed"
        ):
            run_equity_options_backtest(
                self.equity,
                calls_only,
                train_size=24,
                validation_size=14,
                holding_size=8,
                embargo_size=2,
                exchange_sessions=self.sessions,
            )


if __name__ == "__main__":
    unittest.main()
