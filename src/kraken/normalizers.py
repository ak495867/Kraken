from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from kraken.audit import configuration_fingerprint
from kraken.io import _read_csv, observation_from_mapping, option_quote_from_mapping
from kraken.models import NormalizedExportReport, VendorMappingPlugin


CANONICAL_MAPPING = {
    "equity": {
        "timestamp": "timestamp",
        "available_at": "available_at",
        "close": "close",
        "volume": "volume",
        "realized_volatility": "realized_volatility",
        "liquidity": "liquidity",
    },
    "options": {
        "timestamp": "timestamp",
        "available_at": "available_at",
        "expiration": "expiration",
        "contract": "contract",
        "option_type": "option_type",
        "strike": "strike",
        "bid": "bid",
        "ask": "ask",
        "implied_volatility": "implied_volatility",
        "open_interest": "open_interest",
        "volume": "volume",
        "underlying": "underlying",
    },
}


def _default_plugin_root() -> Path:
    candidates = (
        Path(__file__).resolve().parent / "vendor_plugins",
        Path(__file__).resolve().parent.parent / "vendor_plugins",
        Path(__file__).resolve().parents[2] / "vendor_plugins",
    )
    return next((candidate for candidate in candidates if candidate.is_dir()), candidates[0])


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_mapping(mapping: object) -> dict[str, dict[str, str]]:
    if not isinstance(mapping, dict):
        raise ValueError("Vendor mapping must contain equity and options objects")
    validated: dict[str, dict[str, str]] = {}
    for label, canonical_fields in CANONICAL_MAPPING.items():
        fields = mapping.get(label)
        if not isinstance(fields, dict) or set(fields) != set(canonical_fields):
            raise ValueError(f"Vendor mapping {label} fields must exactly match Kraken’s canonical {label} schema")
        if not all(isinstance(source_name, str) and source_name.strip() for source_name in fields.values()):
            raise ValueError(f"Vendor mapping {label} source fields must be non-empty strings")
        validated[label] = {str(target): str(source) for target, source in fields.items()}
    return validated


def _plugin_manifest_paths(plugin_root: Path) -> tuple[Path, ...]:
    if not plugin_root.is_dir():
        return ()
    return tuple(sorted(plugin_root.glob("*/*/plugin.json")))


def discover_vendor_plugins(plugin_root: str | Path | None = None) -> tuple[VendorMappingPlugin, ...]:
    root = Path(plugin_root).expanduser().resolve() if plugin_root is not None else _default_plugin_root()
    plugins: list[VendorMappingPlugin] = []
    seen: set[tuple[str, str]] = set()
    for manifest_path in _plugin_manifest_paths(root):
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Vendor plugin manifest must be an object: {manifest_path}")
        provider = payload.get("provider")
        version = payload.get("version")
        schema = payload.get("schema")
        if not isinstance(provider, str) or not provider.strip() or not isinstance(version, str) or not version.strip() or schema != "kraken_vendor_mapping_plugin/v1":
            raise ValueError(f"Vendor plugin metadata is invalid: {manifest_path}")
        contract_path = manifest_path.with_name("fixture_contract.json")
        if not contract_path.is_file():
            raise ValueError(f"Vendor plugin fixture contract is missing: {contract_path}")
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        if not isinstance(contract, dict) or contract.get("provider") != provider or contract.get("version") != version:
            raise ValueError(f"Vendor plugin fixture contract does not match manifest: {manifest_path}")
        mapping = _validate_mapping(payload.get("mapping"))
        for label in CANONICAL_MAPPING:
            field_name = "required_option_source_fields" if label == "options" else "required_equity_source_fields"
            fields = contract.get(field_name)
            expected = set(mapping[label].values())
            if not isinstance(fields, list) or set(fields) != expected or not all(isinstance(item, str) and item.strip() for item in fields):
                raise ValueError(f"Vendor plugin fixture contract fields do not match manifest: {manifest_path}")
        key = (provider, version)
        if key in seen:
            raise ValueError(f"Duplicate vendor plugin provider and version: {provider} {version}")
        seen.add(key)
        plugins.append(
            VendorMappingPlugin(
                provider=provider,
                version=version,
                schema=schema,
                mapping=mapping,
                plugin_path=str(manifest_path),
                contract_path=str(contract_path),
                sha256=_sha256(manifest_path),
            )
        )
    return tuple(sorted(plugins, key=lambda item: (item.provider, item.version)))


def load_vendor_plugin(profile: str, version: str | None = None, plugin_root: str | Path | None = None) -> VendorMappingPlugin:
    normalized_provider = profile.strip().lower()
    candidates = [item for item in discover_vendor_plugins(plugin_root) if item.provider == normalized_provider and (version is None or item.version == version)]
    if not candidates:
        available = ", ".join(available_profiles(plugin_root)) or "none"
        raise ValueError(f"Unsupported normalizer profile: {profile}. Available profiles: {available}")
    return sorted(candidates, key=lambda item: item.version)[-1]


def available_profiles(plugin_root: str | Path | None = None) -> tuple[str, ...]:
    return tuple(sorted({item.provider for item in discover_vendor_plugins(plugin_root)}))


def load_mapping_file(path: str | Path) -> tuple[str, dict[str, dict[str, str]]]:
    source = Path(path).expanduser().resolve()
    with source.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("Mapping file must contain a JSON object")
    name = str(payload.get("name", source.stem)).strip()
    if not name:
        raise ValueError("Mapping file name must be non-empty")
    return name, _validate_mapping(payload)


def _canonical_rows(rows: list[dict[str, str]], mapping: dict[str, str], label: str) -> list[dict[str, str]]:
    if not rows:
        raise ValueError(f"{label} export must contain at least one row")
    missing = [source for source in mapping.values() if source not in rows[0]]
    if missing:
        raise ValueError(f"{label} export is missing mapped source fields: {', '.join(missing)}")
    canonical: list[dict[str, str]] = []
    for row_number, row in enumerate(rows, 2):
        missing = [source for source in mapping.values() if source not in row]
        if missing:
            raise ValueError(f"{label} export row {row_number} is missing mapped source fields: {', '.join(missing)}")
        canonical.append({target: row[source] for target, source in mapping.items()})
    return canonical


def _write_rows(path: Path, fields: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def normalize_provider_exports(
    profile: str,
    equity_source: str | Path,
    options_source: str | Path,
    output_directory: str | Path,
    mapping_file: str | Path | None = None,
    plugin_version: str | None = None,
    plugin_root: str | Path | None = None,
) -> NormalizedExportReport:
    normalized_profile = profile.strip().lower()
    plugin: VendorMappingPlugin | None = None
    if mapping_file is not None:
        normalized_profile, mapping = load_mapping_file(mapping_file)
    else:
        plugin = load_vendor_plugin(normalized_profile, plugin_version, plugin_root)
        normalized_profile = plugin.provider
        mapping = plugin.mapping
    equity_rows = _canonical_rows(_read_csv(Path(equity_source).expanduser().resolve()), mapping["equity"], "Equity")
    option_rows = _canonical_rows(_read_csv(Path(options_source).expanduser().resolve()), mapping["options"], "Option")
    for index, row in enumerate(equity_rows, 2):
        observation_from_mapping(row, index)
    for index, row in enumerate(option_rows, 2):
        option_quote_from_mapping(row, index)
    destination = Path(output_directory).expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    equity_path = destination / "equity_normalized.csv"
    options_path = destination / "options_normalized.csv"
    _write_rows(equity_path, tuple(CANONICAL_MAPPING["equity"]), equity_rows)
    _write_rows(options_path, tuple(CANONICAL_MAPPING["options"]), option_rows)
    return NormalizedExportReport(
        provider_profile=normalized_profile,
        equity_output_path=str(equity_path),
        options_output_path=str(options_path),
        equity_row_count=len(equity_rows),
        option_row_count=len(option_rows),
        configuration_fingerprint=configuration_fingerprint(
            {
                "profile": normalized_profile,
                "plugin_version": plugin.version if plugin else None,
                "plugin_sha256": plugin.sha256 if plugin else None,
                "mapping_file": str(Path(mapping_file).expanduser().resolve()) if mapping_file is not None else None,
                "equity_source": str(Path(equity_source).expanduser().resolve()),
                "options_source": str(Path(options_source).expanduser().resolve()),
                "equity_row_count": len(equity_rows),
                "option_row_count": len(option_rows),
            }
        ),
        plugin_version=plugin.version if plugin else None,
        plugin_sha256=plugin.sha256 if plugin else None,
        contract_path=plugin.contract_path if plugin else None,
    )
