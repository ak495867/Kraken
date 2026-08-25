from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

from .calendar import load_exchange_calendar, validate_market_data_quality
from .corporate_actions import validate_corporate_action_integrity
from .distributions import validate_distribution_integrity
from .earnings import validate_earnings_event_integrity
from .io import parse_timestamp
from .models import LicensedDataAcceptanceReport, MarketDataQualityPolicy
from .provenance import file_sha256
from .vendor import FilePointInTimeVendorAdapter


def _load_authorization(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.is_file():
        raise ValueError("Licensed acceptance data requires an explicit local authorization attestation file")
    loaded = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("Licensed acceptance authorization must be a JSON object")
    if loaded.get("license_accepted") is not True:
        raise ValueError("Licensed acceptance authorization must set license_accepted to true")
    if not isinstance(loaded.get("authorized_by"), str) or not loaded["authorized_by"].strip():
        raise ValueError("Licensed acceptance authorization must identify authorized_by")
    if not isinstance(loaded.get("dataset_id"), str) or not loaded["dataset_id"].strip():
        raise ValueError("Licensed acceptance authorization must identify dataset_id")
    if not isinstance(loaded.get("expected"), dict):
        raise ValueError("Licensed acceptance authorization must include an expected object")
    if not isinstance(loaded.get("manifest_sha256"), str) or len(loaded["manifest_sha256"]) != 64:
        raise ValueError("Licensed acceptance authorization must include manifest_sha256")
    if not isinstance(loaded.get("files"), dict) or not loaded["files"]:
        raise ValueError("Licensed acceptance authorization must include a files hash object")
    if not isinstance(loaded.get("authorized_at"), str) or not loaded["authorized_at"].strip():
        raise ValueError("Licensed acceptance authorization must include authorized_at")
    if not isinstance(loaded.get("license_name"), str) or not loaded["license_name"].strip():
        raise ValueError("Licensed acceptance authorization must include license_name")
    if not isinstance(loaded.get("expires_at"), str) or not loaded["expires_at"].strip():
        raise ValueError("Licensed acceptance authorization must include expires_at")
    authorized_at_ms = parse_timestamp(loaded["authorized_at"])
    expires_at_ms = parse_timestamp(loaded["expires_at"])
    if expires_at_ms <= authorized_at_ms:
        raise ValueError("Licensed acceptance authorization expires before it was issued")
    if expires_at_ms <= int(time.time() * 1000):
        raise ValueError("Licensed acceptance authorization has expired")
    return loaded


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _verified_input_hashes(manifest_path: str | Path, authorization_path: str | Path, authorization: dict[str, Any], dataset: Any) -> tuple[str, str, tuple[tuple[str, str], ...]]:
    manifest_source = Path(manifest_path).expanduser().resolve()
    manifest_hash = file_sha256(manifest_source)
    if not _is_sha256(authorization["manifest_sha256"]) or authorization["manifest_sha256"] != manifest_hash:
        raise ValueError("Licensed acceptance manifest_sha256 does not match the supplied manifest")
    expected_paths = {
        "equity": dataset.manifest.equity_path,
        "options": dataset.manifest.options_path,
        "corporate_actions": dataset.manifest.corporate_actions_path,
        "option_adjustments": dataset.manifest.option_adjustments_path,
        "distributions": dataset.manifest.distributions_path,
        "earnings": dataset.manifest.earnings_path,
        "mapping": dataset.manifest.mapping_path,
    }
    expected_paths = {key: path for key, path in expected_paths.items() if path is not None}
    attested_files = authorization["files"]
    if set(attested_files) != set(expected_paths):
        raise ValueError("Licensed acceptance files must exactly cover every manifest input")
    hashes: list[tuple[str, str]] = []
    for key, path in expected_paths.items():
        digest = attested_files[key]
        if not _is_sha256(digest) or digest != file_sha256(path):
            raise ValueError(f"Licensed acceptance file hash does not match {key}")
        hashes.append((key, digest))
    return file_sha256(authorization_path), manifest_hash, tuple(hashes)


def _required_int(expected: dict[str, Any], name: str) -> int:
    value = expected.get(name)
    if not isinstance(value, int) or value < 1:
        raise ValueError(f"Licensed acceptance expected.{name} must be an integer of at least one")
    return value


def run_licensed_data_acceptance(
    manifest_path: str | Path,
    authorization_path: str | Path,
    calendar_path: str | Path,
    max_snapshot_lag_ms: int = 300000,
) -> LicensedDataAcceptanceReport:
    authorization = _load_authorization(authorization_path)
    expected = authorization["expected"]
    required_actions = _required_int(expected, "minimum_corporate_actions")
    required_adjustments = _required_int(expected, "minimum_option_adjustments")
    missing_contracts = expected.get("missing_contracts")
    earnings_revisions = expected.get("earnings_revisions")
    half_day_dates = expected.get("half_day_dates")
    if not isinstance(missing_contracts, list) or not missing_contracts or not all(isinstance(item, str) and item for item in missing_contracts):
        raise ValueError("Licensed acceptance expected.missing_contracts must list at least one contract intentionally absent from the authorized sample")
    if not isinstance(earnings_revisions, list) or not earnings_revisions:
        raise ValueError("Licensed acceptance expected.earnings_revisions must list at least one authorized revision expectation")
    if not isinstance(half_day_dates, list) or not half_day_dates or not all(isinstance(item, str) and item for item in half_day_dates):
        raise ValueError("Licensed acceptance expected.half_day_dates must list at least one declared half-day session")
    dataset = FilePointInTimeVendorAdapter(manifest_path).load()
    authorization_sha256, manifest_sha256, input_sha256 = _verified_input_hashes(manifest_path, authorization_path, authorization, dataset)
    if authorization["dataset_id"] != dataset.manifest.dataset_id:
        raise ValueError("Licensed acceptance authorization dataset_id does not match the vendor manifest")
    if len(dataset.corporate_actions) < required_actions:
        raise ValueError("Authorized acceptance sample lacks the declared minimum corporate-action cases")
    if len(dataset.option_adjustments) < required_adjustments:
        raise ValueError("Authorized acceptance sample lacks the declared minimum option-adjustment cases")
    sessions = load_exchange_calendar(calendar_path)
    declared_half_days = {item.session_date for item in sessions if item.is_half_day}
    if not set(half_day_dates).issubset(declared_half_days):
        raise ValueError("Authorized acceptance calendar does not contain every declared half-day session")
    cutoff = dataset.manifest.snapshot_as_of_ms
    corporate = validate_corporate_action_integrity(
        dataset.equity,
        dataset.options,
        dataset.corporate_actions,
        dataset.option_adjustments,
        cutoff,
        dataset.manifest.price_basis,
    )
    if not corporate.valid:
        details = "; ".join(item.message for item in corporate.issues)
        raise ValueError(f"Authorized corporate-action acceptance check failed: {details}")
    distributions = validate_distribution_integrity(dataset.equity, dataset.distributions, cutoff, dataset.manifest.price_basis)
    if not distributions.valid:
        details = "; ".join(item.message for item in distributions.issues)
        raise ValueError(f"Authorized distribution acceptance check failed: {details}")
    earnings = validate_earnings_event_integrity(dataset.earnings_events, cutoff)
    if not earnings.valid:
        details = "; ".join(item.message for item in earnings.issues)
        raise ValueError(f"Authorized earnings availability acceptance check failed: {details}")
    revision_counts = Counter((item.underlying, item.fiscal_period) for item in dataset.earnings_events)
    for expectation in earnings_revisions:
        if not isinstance(expectation, dict):
            raise ValueError("Each earnings revision expectation must be an object")
        underlying = expectation.get("underlying")
        fiscal_period = expectation.get("fiscal_period")
        minimum_events = expectation.get("minimum_events")
        if not isinstance(underlying, str) or not isinstance(fiscal_period, str) or not isinstance(minimum_events, int) or minimum_events < 2:
            raise ValueError("Each earnings revision expectation requires underlying, fiscal_period, and minimum_events of at least two")
        if revision_counts[(underlying, fiscal_period)] < minimum_events:
            raise ValueError(f"Authorized acceptance sample lacks declared earnings revisions for {underlying} {fiscal_period}")
    available_contracts = {item.contract for item in dataset.options}
    present_missing = sorted(set(missing_contracts) & available_contracts)
    if present_missing:
        raise ValueError(f"Contracts declared missing are present in the authorized sample: {', '.join(present_missing)}")
    quality = validate_market_data_quality(
        dataset.equity,
        dataset.options,
        cutoff,
        sessions,
        MarketDataQualityPolicy(max_snapshot_lag_ms=max_snapshot_lag_ms, strict=True),
    )
    if not quality.valid:
        details = "; ".join(item.message for item in quality.issues)
        raise ValueError(f"Authorized calendar and missing-data acceptance check failed: {details}")
    verified_checks = (
        "authorization_attestation",
        "corporate_actions",
        "option_adjustments",
        "earnings_event_availability",
        "earnings_revisions",
        "declared_missing_quotes",
        "exchange_calendar_and_half_days",
        "stale_and_duplicate_snapshot_controls",
        "option_chain_completeness",
    )
    return LicensedDataAcceptanceReport(
        provider=dataset.manifest.provider,
        dataset_id=dataset.manifest.dataset_id,
        accepted=True,
        verified_checks=verified_checks,
        warnings=quality.warnings,
        authorization_sha256=authorization_sha256,
        manifest_sha256=manifest_sha256,
        input_sha256=input_sha256,
        license_name=authorization["license_name"],
        authorized_by=authorization["authorized_by"],
        authorized_at=authorization["authorized_at"],
        expires_at=authorization["expires_at"],
    )
