from __future__ import annotations

import argparse
import json

from kraken.acceptance import run_licensed_data_acceptance
from kraken.models import to_primitive


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="run_licensed_acceptance",
        description="Run an opt-in acceptance suite against user-authorized licensed local point-in-time data",
    )
    parser.add_argument(
        "--manifest", required=True, help="Local licensed vendor manifest JSON"
    )
    parser.add_argument(
        "--authorization",
        required=True,
        help="Local license-acceptance attestation JSON",
    )
    parser.add_argument(
        "--calendar", required=True, help="Local explicit exchange calendar JSON or CSV"
    )
    parser.add_argument(
        "--max-snapshot-lag-ms",
        type=int,
        default=300000,
        help="Maximum permitted source-publication lag",
    )
    args = parser.parse_args()
    report = run_licensed_data_acceptance(
        args.manifest, args.authorization, args.calendar, args.max_snapshot_lag_ms
    )
    print(json.dumps(to_primitive(report), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
