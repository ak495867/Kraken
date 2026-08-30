from __future__ import annotations

import hashlib
import json
import platform
from dataclasses import replace
from pathlib import Path
from typing import Any, Iterable

from .models import ResearchRunComparison, RunManifest, to_primitive

ENGINE_VERSION = "0.1.0"


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        to_primitive(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).expanduser().resolve().open("rb") as handle:
        for block in iter(lambda: handle.read(1_048_576), b""):
            digest.update(block)
    return digest.hexdigest()


def _identity_payload(manifest: RunManifest) -> dict[str, Any]:
    return {
        "engine_version": manifest.engine_version,
        "decision_cutoff_ms": manifest.decision_cutoff_ms,
        "configuration_sha256": manifest.configuration_sha256,
        "input_sha256": manifest.input_sha256,
        "output_sha256": manifest.output_sha256,
        "vendor_manifest_sha256": manifest.vendor_manifest_sha256,
        "environment": {
            "platform": manifest.platform,
            "python_version": manifest.python_version,
            "compiler": manifest.compiler,
        },
    }


def verify_run_manifest(manifest: RunManifest, output: Any | None = None) -> None:
    if canonical_sha256(_identity_payload(manifest)) != manifest.run_id:
        raise ValueError("Run manifest identity hash does not match its fields")
    if output is not None:
        candidate = (
            replace(output, manifest=None) if hasattr(output, "manifest") else output
        )
        if canonical_sha256(candidate) != manifest.output_sha256:
            raise ValueError("Run manifest output hash does not match the report")


def load_run_manifest(path: str | Path) -> RunManifest:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise ValueError(f"Run manifest does not exist: {source}")
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Run manifest must be a JSON object")
    required = {
        "run_id",
        "engine_version",
        "decision_cutoff_ms",
        "configuration_sha256",
        "input_sha256",
        "output_sha256",
        "vendor_manifest_sha256",
        "platform",
        "python_version",
        "compiler",
        "warnings",
    }
    if set(payload) != required:
        raise ValueError(
            "Run manifest fields do not match the immutable Kraken manifest schema"
        )
    input_sha256 = payload["input_sha256"]
    warnings = payload["warnings"]
    if not isinstance(input_sha256, list) or not all(
        isinstance(item, list)
        and len(item) == 2
        and all(isinstance(part, str) for part in item)
        for item in input_sha256
    ):
        raise ValueError("Run manifest input_sha256 must contain name and hash pairs")
    if not isinstance(warnings, list) or not all(
        isinstance(item, str) for item in warnings
    ):
        raise ValueError("Run manifest warnings must be a string list")
    if payload["decision_cutoff_ms"] is not None and not isinstance(
        payload["decision_cutoff_ms"], int
    ):
        raise ValueError("Run manifest decision_cutoff_ms must be an integer or null")
    text_fields = required - {
        "decision_cutoff_ms",
        "input_sha256",
        "warnings",
        "vendor_manifest_sha256",
    }
    if not all(
        isinstance(payload[field], str) and payload[field] for field in text_fields
    ):
        raise ValueError("Run manifest has invalid required text fields")
    if payload["vendor_manifest_sha256"] is not None and not isinstance(
        payload["vendor_manifest_sha256"], str
    ):
        raise ValueError("Run manifest vendor_manifest_sha256 must be a string or null")
    manifest = RunManifest(
        run_id=payload["run_id"],
        engine_version=payload["engine_version"],
        decision_cutoff_ms=payload["decision_cutoff_ms"],
        configuration_sha256=payload["configuration_sha256"],
        input_sha256=tuple((item[0], item[1]) for item in input_sha256),
        output_sha256=payload["output_sha256"],
        vendor_manifest_sha256=payload["vendor_manifest_sha256"],
        platform=payload["platform"],
        python_version=payload["python_version"],
        compiler=payload["compiler"],
        warnings=tuple(warnings),
    )
    verify_run_manifest(manifest)
    return manifest


def create_run_manifest(
    configuration: Any,
    named_inputs: dict[str, Any],
    output: Any,
    decision_cutoff_ms: int | None,
    vendor_manifest_path: str | None = None,
    warnings: Iterable[str] = (),
) -> RunManifest:
    configuration_sha256 = canonical_sha256(configuration)
    input_sha256 = tuple(
        sorted((name, canonical_sha256(value)) for name, value in named_inputs.items())
    )
    output_sha256 = canonical_sha256(output)
    vendor_manifest_sha256 = (
        file_sha256(vendor_manifest_path) if vendor_manifest_path is not None else None
    )
    environment = {
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "compiler": platform.python_compiler(),
    }
    manifest = RunManifest(
        run_id="",
        engine_version=ENGINE_VERSION,
        decision_cutoff_ms=decision_cutoff_ms,
        configuration_sha256=configuration_sha256,
        input_sha256=input_sha256,
        output_sha256=output_sha256,
        vendor_manifest_sha256=vendor_manifest_sha256,
        platform=environment["platform"],
        python_version=environment["python_version"],
        compiler=environment["compiler"],
        warnings=tuple(warnings),
    )
    return replace(manifest, run_id=canonical_sha256(_identity_payload(manifest)))


def compare_run_manifests(
    left: RunManifest, right: RunManifest
) -> ResearchRunComparison:
    configuration_changed = left.configuration_sha256 != right.configuration_sha256
    input_changed = (
        left.input_sha256 != right.input_sha256
        or left.vendor_manifest_sha256 != right.vendor_manifest_sha256
    )
    output_changed = left.output_sha256 != right.output_sha256
    environment_changed = (
        left.engine_version,
        left.platform,
        left.python_version,
        left.compiler,
    ) != (right.engine_version, right.platform, right.python_version, right.compiler)
    summary: list[str] = []
    if configuration_changed:
        summary.append("Configuration fingerprint changed")
    if input_changed:
        summary.append("Input or vendor-manifest fingerprint changed")
    if environment_changed:
        summary.append("Engine or execution environment changed")
    if output_changed:
        summary.append("Output fingerprint changed")
    if not summary:
        summary.append("Manifests are identical")
    return ResearchRunComparison(
        left.run_id,
        right.run_id,
        configuration_changed,
        input_changed,
        output_changed,
        environment_changed,
        tuple(summary),
    )
