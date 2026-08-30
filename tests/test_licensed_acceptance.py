import json
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from kraken.acceptance import run_licensed_data_acceptance
from kraken.provenance import file_sha256


class LicensedAcceptanceTests(unittest.TestCase):
    def test_acceptance_rejects_manifest_hash_mismatch(self):
        authorization = {
            "license_accepted": True,
            "authorized_by": "test-owner",
            "authorized_at": "2026-01-01T00:00:00Z",
            "expires_at": "2100-01-01T00:00:00Z",
            "license_name": "test-license",
            "dataset_id": "illustrative-pit-equity-options",
            "manifest_sha256": "0" * 64,
            "files": {"equity": "0" * 64},
            "expected": {
                "minimum_corporate_actions": 1,
                "minimum_option_adjustments": 1,
                "earnings_revisions": [
                    {
                        "underlying": "ILLUS",
                        "fiscal_period": "2025Q1",
                        "minimum_events": 2,
                    }
                ],
                "missing_contracts": ["MISSING"],
                "half_day_dates": ["2025-01-03"],
            },
        }
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "authorization.json"
            path.write_text(json.dumps(authorization), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "manifest_sha256"):
                run_licensed_data_acceptance(
                    root / "fixtures" / "illustrative_vendor_manifest.json",
                    path,
                    root / "missing-calendar.json",
                )

    def test_valid_acceptance_reports_verified_lineage(self):
        root = Path(__file__).resolve().parents[1]
        source_manifest = json.loads(
            (root / "fixtures" / "illustrative_vendor_manifest.json").read_text(
                encoding="utf-8"
            )
        )
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            for name in (
                "illustrative_market_data.csv",
                "illustrative_option_quotes.csv",
                "illustrative_corporate_actions.csv",
                "illustrative_option_adjustments.csv",
                "illustrative_distributions.csv",
                "illustrative_snapshot_equity.csv",
                "illustrative_snapshot_options.csv",
            ):
                shutil.copy2(root / "fixtures" / name, workspace / name)
            (workspace / "illustrative_earnings_events.csv").write_text(
                "event_at,available_at,underlying,fiscal_period,event_type\n"
                "2025-02-21T00:00:00Z,2025-02-21T00:00:00Z,ILLUS,2025Q1,earnings_revision\n"
                "2025-02-22T00:00:00Z,2025-02-22T00:00:00Z,ILLUS,2025Q1,earnings_revision\n",
                encoding="utf-8",
            )
            (workspace / "licensed_snapshot_v1.json").write_text(
                json.dumps(
                    {
                        "name": "licensed_snapshot_v1",
                        "equity": {
                            "timestamp": "event_time",
                            "available_at": "published_at",
                            "close": "settle",
                            "volume": "shares",
                            "realized_volatility": "rv_20d",
                            "liquidity": "notional_liquidity",
                        },
                        "options": {
                            "timestamp": "event_time",
                            "available_at": "published_at",
                            "expiration": "expiry",
                            "contract": "symbol",
                            "option_type": "right",
                            "strike": "exercise_price",
                            "bid": "best_bid",
                            "ask": "best_ask",
                            "implied_volatility": "iv",
                            "open_interest": "open_int",
                            "volume": "contracts",
                            "underlying": "root",
                        },
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            manifest_payload = {
                "provider": "Illustrative Licensed Export",
                "dataset_id": "acceptance-test-dataset",
                "snapshot_as_of": "2025-04-07T00:00:00Z",
                "price_basis": "split_adjusted",
                "equity_path": "illustrative_market_data.csv",
                "options_path": "illustrative_option_quotes.csv",
                "corporate_actions_path": "illustrative_corporate_actions.csv",
                "option_adjustments_path": "illustrative_option_adjustments.csv",
                "distributions_path": "illustrative_distributions.csv",
                "earnings_path": "illustrative_earnings_events.csv",
                "mapping_path": "licensed_snapshot_v1.json",
                "normalizer_profile": "licensed_snapshot_v1",
            }
            manifest_path = workspace / "manifest.json"
            manifest_path.write_text(
                json.dumps(manifest_payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            start = datetime(2025, 1, 2, tzinfo=timezone.utc)
            sessions = []
            for index in range(96):
                session = start + timedelta(days=index)
                open_ms = int(session.timestamp() * 1000)
                sessions.append(
                    {
                        "session_date": session.date().isoformat(),
                        "open_ms": open_ms,
                        "close_ms": open_ms + 86_399_999,
                        "is_half_day": index == 1,
                    }
                )
            calendar_path = workspace / "calendar.json"
            calendar_path.write_text(json.dumps(sessions), encoding="utf-8")
            file_paths = {
                "equity": workspace / "illustrative_market_data.csv",
                "options": workspace / "illustrative_option_quotes.csv",
                "corporate_actions": workspace / "illustrative_corporate_actions.csv",
                "option_adjustments": workspace / "illustrative_option_adjustments.csv",
                "distributions": workspace / "illustrative_distributions.csv",
                "earnings": workspace / "illustrative_earnings_events.csv",
                "mapping": workspace / "licensed_snapshot_v1.json",
            }
            authorization = {
                "license_accepted": True,
                "authorized_by": "test-owner",
                "authorized_at": "2026-01-01T00:00:00Z",
                "expires_at": "2100-01-01T00:00:00Z",
                "license_name": "test-license",
                "dataset_id": "acceptance-test-dataset",
                "manifest_sha256": file_sha256(manifest_path),
                "files": {key: file_sha256(path) for key, path in file_paths.items()},
                "expected": {
                    "minimum_corporate_actions": 1,
                    "minimum_option_adjustments": 1,
                    "earnings_revisions": [
                        {
                            "underlying": "ILLUS",
                            "fiscal_period": "2025Q1",
                            "minimum_events": 2,
                        }
                    ],
                    "missing_contracts": ["MISSING"],
                    "half_day_dates": ["2025-01-03"],
                },
            }
            authorization_path = workspace / "authorization.json"
            authorization_path.write_text(
                json.dumps(authorization, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            report = run_licensed_data_acceptance(
                manifest_path, authorization_path, calendar_path
            )
            self.assertTrue(report.accepted)
            self.assertEqual(report.dataset_id, "acceptance-test-dataset")
            self.assertEqual(len(report.input_sha256), 7)
            self.assertEqual(
                report.authorization_sha256, file_sha256(authorization_path)
            )

    def test_acceptance_requires_explicit_authorization_file(self):
        absent = (
            Path(__file__).resolve().parents[1]
            / "acceptance_data"
            / "authorization.json"
        )
        with self.assertRaisesRegex(
            ValueError, "explicit local authorization attestation"
        ):
            run_licensed_data_acceptance(
                "missing-manifest.json", absent, "missing-calendar.json"
            )


if __name__ == "__main__":
    unittest.main()
