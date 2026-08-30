from __future__ import annotations

import argparse
import csv
import statistics
import subprocess
from pathlib import Path

REQUIRED_COLUMNS = (
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
)


def read_csv(path: Path) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != REQUIRED_COLUMNS:
            raise ValueError("Benchmark output schema is invalid")
        rows = {row["benchmark"]: row for row in reader}
    if not rows:
        raise ValueError("Benchmark output is empty")
    return rows


def stable_benchmark(
    executable: str, observations: int, iterations: int, samples: int, attempts: int
) -> list[dict[str, str]]:
    if observations < 32 or iterations < 1 or samples < 3 or attempts < 3:
        raise ValueError("Benchmark dimensions and attempts are invalid")
    results: list[dict[str, dict[str, str]]] = []
    for _ in range(attempts):
        temporary = Path.cwd() / ".kraken-benchmark.csv"
        with temporary.open("w", encoding="utf-8") as output:
            subprocess.run(
                [executable, str(observations), str(iterations), str(samples)],
                check=True,
                stdout=output,
                text=True,
            )
        results.append(read_csv(temporary))
        temporary.unlink()
    keys = set(results[0])
    if any(set(result) != keys for result in results[1:]):
        raise ValueError("Benchmark attempts returned different workloads")
    stable: list[dict[str, str]] = []
    for key in sorted(keys):
        first = results[0][key]
        row = dict(first)
        p50_values = [float(result[key]["p50_ms"]) for result in results]
        p95_values = [float(result[key]["p95_ms"]) for result in results]
        row["p50_ms"] = f"{statistics.median(p50_values):.3f}"
        row["p95_ms"] = f"{statistics.median(p95_values):.3f}"
        stable.append(row)
    return stable


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the Kraken native benchmark repeatedly and aggregate stable median timings"
    )
    parser.add_argument("--benchmark", required=True)
    parser.add_argument("--observations", type=int, default=200000)
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--samples", type=int, default=9)
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    rows = stable_benchmark(
        args.benchmark, args.observations, args.iterations, args.samples, args.attempts
    )
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REQUIRED_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
