# Authorized Licensed-Data Acceptance Contract

Kraken’s acceptance harness is intentionally **empty by default**. It must be run only against a local point-in-time sample that the operator is authorized to use for validation. The repository provides no proprietary sample, credentials, vendor connector, or synthetic stand-in that could be mistaken for a licensed dataset.

| Required local artifact | Required content | Failure behavior |
| --- | --- | --- |
| Vendor manifest | Kraken’s local licensed-data manifest and paths to authorized exports. | The adapter rejects absent files or data later than `snapshot_as_of`. |
| Calendar | JSON or CSV sessions with `session_date`, `open_ms`, `close_ms`, and `is_half_day`. | The harness rejects missing, duplicate, invalid, or undeclared half-day sessions. |
| Authorization attestation | JSON object with `license_accepted: true`, `authorized_by`, `dataset_id`, `authorized_at`, future `expires_at`, `license_name`, `manifest_sha256`, a `files` hash object, and an `expected` contract. | The harness refuses to start without it, rejects expired attestations, and rejects any changed manifest or input file. |

The attestation’s `expected` object must declare `minimum_corporate_actions`, `minimum_option_adjustments`, `earnings_revisions`, `missing_contracts`, and `half_day_dates`. An earnings revision expectation contains `underlying`, `fiscal_period`, and `minimum_events` of at least two. A missing contract is a contract identifier deliberately absent from the authorized sample; the harness fails if it is present. The `files` object must contain exactly one lowercase SHA-256 digest for every file referenced by the vendor manifest, including the mapping file when present.

```json
{
  "license_accepted": true,
  "authorized_by": "data-governance-owner",
  "authorized_at": "2026-01-01T00:00:00Z",
  "expires_at": "2027-01-01T00:00:00Z",
  "license_name": "Authorized vendor research license",
  "dataset_id": "authorized-point-in-time-sample",
  "manifest_sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "files": {
    "equity": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    "options": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    "corporate_actions": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    "option_adjustments": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    "distributions": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    "earnings": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    "mapping": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
  },
  "expected": {
    "minimum_corporate_actions": 1,
    "minimum_option_adjustments": 1,
    "earnings_revisions": [
      {"underlying": "EXAMPLE", "fiscal_period": "2025Q1", "minimum_events": 2}
    ],
    "missing_contracts": ["EXAMPLE_EXPECTED_ABSENT_CONTRACT"],
    "half_day_dates": ["2025-11-28"]
  }
}
```

Use `tools/create_authorization_attestation.py` to generate the manifest and input-file hashes, then review and authorize the resulting JSON before running the harness. The harness validates corporate actions, option adjustments, earnings availability and revisions, declared missing quotes, exchange sessions and half days, stale and duplicate snapshots, and option-chain completeness. The output is a local JSON acceptance report; it contains no trading recommendations.

```bash
python tools/create_authorization_attestation.py \
  --manifest authorized_vendor_manifest.json \
  --authorized-by data-governance-owner \
  --license-name "Authorized vendor research license" \
  --expires-at 2027-01-01T00:00:00Z \
  --expected acceptance_expected.json \
  --output authorized_acceptance.json

python tools/run_licensed_acceptance.py \
  --manifest authorized_vendor_manifest.json \
  --authorization authorized_acceptance.json \
  --calendar authorized_exchange_calendar.json
```
