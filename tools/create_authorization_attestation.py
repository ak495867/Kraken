import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from kraken.io import load_vendor_manifest
from kraken.provenance import file_sha256


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a local licensed-data authorization attestation")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--authorized-by", required=True)
    parser.add_argument("--license-name", required=True)
    parser.add_argument("--expires-at", required=True)
    parser.add_argument("--expected", required=True, help="JSON file containing the acceptance expected object")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    manifest_path = Path(args.manifest).expanduser().resolve()
    manifest = load_vendor_manifest(manifest_path)
    expected = json.loads(Path(args.expected).expanduser().resolve().read_text(encoding="utf-8"))
    if not isinstance(expected, dict):
        raise ValueError("Expected acceptance contract must be a JSON object")
    paths = {
        "equity": manifest.equity_path,
        "options": manifest.options_path,
        "corporate_actions": manifest.corporate_actions_path,
        "option_adjustments": manifest.option_adjustments_path,
        "distributions": manifest.distributions_path,
        "earnings": manifest.earnings_path,
        "mapping": manifest.mapping_path,
    }
    files = {key: file_sha256(path) for key, path in paths.items() if path is not None}
    payload = {
        "license_accepted": True,
        "authorized_by": args.authorized_by,
        "authorized_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "expires_at": args.expires_at,
        "license_name": args.license_name,
        "dataset_id": manifest.dataset_id,
        "manifest_sha256": file_sha256(manifest_path),
        "files": files,
        "expected": expected,
    }
    Path(args.output).expanduser().resolve().write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
