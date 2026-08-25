from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from . import _core
from .models import ResearchBundleReport, to_primitive
from .provenance import verify_run_manifest


DISCLOSURE = "Kraken is a local-first research toolkit. This bundle documents analytical inputs, safeguards, and reproducibility artifacts. It does not provide investment advice, trading instructions, order handling, portfolio allocation, or profit-and-loss claims."


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _write_json(path: Path, value: Any) -> str:
    rendered = json.dumps(to_primitive(value), sort_keys=True, indent=2) + "\n"
    path.write_text(rendered, encoding="utf-8")
    return _sha256_bytes(rendered.encode("utf-8"))


def _canonical_config(value: str | dict[str, Any]) -> str:
    if isinstance(value, str):
        document = value
    elif isinstance(value, dict):
        document = "".join(f"{key}={value[key]}\n" for key in sorted(value))
    else:
        raise ValueError("Bundle configuration must be a canonical config string or a mapping")
    return _core.serialize_research_config(_core.parse_research_config(document))


def _integrity_payload(report: Any) -> Any:
    integrity = getattr(report, "integrity", None)
    if integrity is not None:
        return integrity
    windows = getattr(report, "windows", None)
    if windows is not None:
        return {"windows": tuple(item.integrity for item in windows)}
    raise ValueError("Research bundle report must expose integrity evidence directly or through windows")


def _copy_optional(source: str | Path | None, destination: Path, hashes: dict[str, str]) -> None:
    if source is None:
        return
    input_path = Path(source).expanduser().resolve()
    if not input_path.is_file():
        raise ValueError(f"Bundle artifact does not exist: {input_path}")
    output_path = destination / input_path.name
    shutil.copyfile(input_path, output_path)
    hashes[output_path.name] = _sha256_bytes(output_path.read_bytes())


def create_research_bundle(
    report: Any,
    output_directory: str | Path,
    canonical_config: str | dict[str, Any],
    chart_path: str | Path | None = None,
    benchmark_context_path: str | Path | None = None,
) -> ResearchBundleReport:
    manifest = getattr(report, "manifest", None)
    if manifest is None:
        raise ValueError("Research bundle requires a report with an immutable run manifest")
    verify_run_manifest(manifest, report)
    destination = Path(output_directory).expanduser().resolve()
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("Research bundle output directory must be empty")
    destination.mkdir(parents=True, exist_ok=True)
    hashes: dict[str, str] = {}
    hashes["report.json"] = _write_json(destination / "report.json", report)
    hashes["run_manifest.json"] = _write_json(destination / "run_manifest.json", manifest)
    hashes["integrity.json"] = _write_json(destination / "integrity.json", _integrity_payload(report))
    warnings = tuple(getattr(report, "warnings", ()))
    hashes["warnings.json"] = _write_json(destination / "warnings.json", {"warnings": warnings})
    config_rendered = _canonical_config(canonical_config)
    (destination / "research_config.kcfg").write_text(config_rendered, encoding="utf-8")
    hashes["research_config.kcfg"] = _sha256_bytes(config_rendered.encode("utf-8"))
    (destination / "RESEARCH_ONLY_DISCLOSURE.md").write_text(DISCLOSURE + "\n", encoding="utf-8")
    hashes["RESEARCH_ONLY_DISCLOSURE.md"] = _sha256_bytes((DISCLOSURE + "\n").encode("utf-8"))
    _copy_optional(chart_path, destination, hashes)
    _copy_optional(benchmark_context_path, destination, hashes)
    bundle_manifest = {
        "bundle_schema": "kraken_research_bundle/v1",
        "run_id": manifest.run_id,
        "run_manifest_sha256": hashes["run_manifest.json"],
        "files": hashes,
    }
    bundle_sha256 = _write_json(destination / "bundle_manifest.json", bundle_manifest)
    return ResearchBundleReport(
        output_directory=str(destination),
        files=tuple(sorted((*hashes, "bundle_manifest.json"))),
        bundle_sha256=bundle_sha256,
        report_manifest_sha256=bundle_manifest["run_manifest_sha256"],
    )
