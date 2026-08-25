from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


REQUIRED_COLUMNS = {
    "benchmark",
    "observations",
    "iterations",
    "samples",
    "p50_ms",
    "p95_ms",
    "checksum",
    "compiler",
    "input_bar_copy_count",
    "input_bar_copy_bytes",
    "temporary_double_buffer_count",
    "temporary_double_buffer_bytes",
}


def read_results(path: str | Path) -> dict[tuple[str, int, int], dict[str, object]]:
    source = Path(path).expanduser().resolve()
    with source.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or set(reader.fieldnames) != REQUIRED_COLUMNS:
            raise ValueError("Benchmark CSV must contain the exact percentile and instrumentation result schema")
        results: dict[tuple[str, int, int], dict[str, object]] = {}
        for row in reader:
            key = (row["benchmark"], int(row["observations"]), int(row["iterations"]))
            p50_ms = float(row["p50_ms"])
            p95_ms = float(row["p95_ms"])
            if p50_ms <= 0.0 or p95_ms <= 0.0 or p95_ms < p50_ms:
                raise ValueError("Benchmark p50_ms and p95_ms must be positive with p95_ms at least p50_ms")
            if key in results:
                raise ValueError("Benchmark CSV contains duplicate benchmark rows")
            results[key] = {
                "samples": int(row["samples"]),
                "p50_ms": p50_ms,
                "p95_ms": p95_ms,
                "checksum": float(row["checksum"]),
                "compiler": row["compiler"],
                "input_bar_copy_count": int(row["input_bar_copy_count"]),
                "input_bar_copy_bytes": int(row["input_bar_copy_bytes"]),
                "temporary_double_buffer_count": int(row["temporary_double_buffer_count"]),
                "temporary_double_buffer_bytes": int(row["temporary_double_buffer_bytes"]),
            }
    if not results:
        raise ValueError("Benchmark CSV must contain at least one result row")
    return results


def _thresholds(policy: dict[str, Any], benchmark: str) -> dict[str, Any]:
    defaults = policy.get("defaults")
    workloads = policy.get("workloads", {})
    if not isinstance(defaults, dict) or not isinstance(workloads, dict):
        raise ValueError("Performance policy requires defaults and workloads objects")
    configured = dict(defaults)
    configured.update(workloads.get(benchmark, {}))
    required = {
        "max_p50_regression_percent",
        "max_p95_regression_percent",
        "max_input_bar_copy_count",
        "max_input_bar_copy_bytes",
    }
    if not required.issubset(configured):
        raise ValueError("Performance policy lacks required percentile or copy thresholds")
    if any(float(configured[name]) < 0.0 for name in required):
        raise ValueError("Performance thresholds must be non-negative")
    return configured


def compare_results(
    baseline: dict[tuple[str, int, int], dict[str, object]],
    candidate: dict[tuple[str, int, int], dict[str, object]],
    policy: dict[str, Any],
) -> dict[str, object]:
    if set(baseline) != set(candidate):
        raise ValueError("Baseline and candidate benchmark keys must match exactly")
    require_matching_compiler = bool(policy.get("require_matching_compiler", False))
    comparisons: list[dict[str, object]] = []
    failing: list[str] = []
    for key in sorted(baseline):
        baseline_row = baseline[key]
        candidate_row = candidate[key]
        thresholds = _thresholds(policy, key[0])
        baseline_p50 = float(baseline_row["p50_ms"])
        baseline_p95 = float(baseline_row["p95_ms"])
        candidate_p50 = float(candidate_row["p50_ms"])
        candidate_p95 = float(candidate_row["p95_ms"])
        p50_regression_percent = (candidate_p50 / baseline_p50 - 1.0) * 100.0
        p95_regression_percent = (candidate_p95 / baseline_p95 - 1.0) * 100.0
        compiler_match = baseline_row["compiler"] == candidate_row["compiler"]
        checksum_match = abs(float(baseline_row["checksum"]) - float(candidate_row["checksum"])) <= 1e-9
        copy_count = int(candidate_row["input_bar_copy_count"])
        copy_bytes = int(candidate_row["input_bar_copy_bytes"])
        passed = (
            checksum_match
            and (not require_matching_compiler or compiler_match)
            and p50_regression_percent <= float(thresholds["max_p50_regression_percent"])
            and p95_regression_percent <= float(thresholds["max_p95_regression_percent"])
            and copy_count <= int(thresholds["max_input_bar_copy_count"])
            and copy_bytes <= int(thresholds["max_input_bar_copy_bytes"])
        )
        label = f"{key[0]}:{key[1]}:{key[2]}"
        if not passed:
            failing.append(label)
        comparisons.append(
            {
                "benchmark": key[0],
                "observations": key[1],
                "iterations": key[2],
                "baseline_p50_ms": baseline_p50,
                "candidate_p50_ms": candidate_p50,
                "p50_regression_percent": p50_regression_percent,
                "baseline_p95_ms": baseline_p95,
                "candidate_p95_ms": candidate_p95,
                "p95_regression_percent": p95_regression_percent,
                "baseline_compiler": baseline_row["compiler"],
                "candidate_compiler": candidate_row["compiler"],
                "compiler_match": compiler_match,
                "checksum_match": checksum_match,
                "candidate_input_bar_copy_count": copy_count,
                "candidate_input_bar_copy_bytes": copy_bytes,
                "temporary_double_buffer_count": candidate_row["temporary_double_buffer_count"],
                "temporary_double_buffer_bytes": candidate_row["temporary_double_buffer_bytes"],
                "thresholds": thresholds,
                "passed": passed,
            }
        )
    return {"passed": not failing, "policy": policy, "comparisons": comparisons, "failing_benchmarks": failing}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare deterministic Kraken native benchmark percentile and instrumentation results")
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--policy", required=True)
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    policy = json.loads(Path(args.policy).expanduser().resolve().read_text(encoding="utf-8"))
    result = compare_results(read_results(args.baseline), read_results(args.candidate), policy)
    rendered = json.dumps(result, sort_keys=True, indent=2)
    if args.output:
        Path(args.output).expanduser().resolve().write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
