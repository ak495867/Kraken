from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .analysis import analyze_regime_risk, run_sonar_tracker
from .audit import build_integrity_audit
from .backtest import run_equity_options_backtest, run_vendor_equity_options_backtest
from .calibration import calibrate_forecast_bands
from .bundles import create_research_bundle
from .calendar import load_exchange_calendar
from .diagnostics import (
    calibration_diagnostics,
    load_backtest_report,
    time_sliced_calibration_diagnostics,
)
from .dynamics import analyze_marine_dynamics
from .io import load_observations, load_option_quotes, parse_timestamp
from .models import MarketDataQualityPolicy, to_primitive
from .normalizers import available_profiles, normalize_provider_exports
from .provenance import compare_run_manifests, load_run_manifest
from .research import run_walk_forward
from .visualizations import render_time_sliced_diagnostics


def _horizons(value: str) -> tuple[int, ...]:
    try:
        parsed = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "Horizons must be comma-separated positive integers"
        ) from exc
    if not parsed or any(item <= 0 for item in parsed):
        raise argparse.ArgumentTypeError(
            "Horizons must be comma-separated positive integers"
        )
    return parsed


def _cutoff(value: str | None, observations) -> int:
    if value is not None:
        return parse_timestamp(value)
    return max(max(item.timestamp_ms, item.available_at_ms) for item in observations)


def _add_common_arguments(
    parser: argparse.ArgumentParser, cutoff_required: bool = False
) -> None:
    parser.add_argument(
        "--input",
        required=True,
        help="Local CSV or JSON input with timestamp and available_at fields",
    )
    parser.add_argument(
        "--format",
        choices=("terminal", "json"),
        default="terminal",
        help="Output rendering format",
    )
    parser.add_argument(
        "--universe-id",
        help="Historical universe identifier for survivorship documentation",
    )
    parser.add_argument(
        "--survivorship-controlled",
        action="store_true",
        help="Declare that supplied data controls the historical universe",
    )
    parser.add_argument(
        "--cutoff",
        required=cutoff_required,
        help="UTC ISO-8601 or Unix millisecond decision cutoff",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kraken",
        description="Research-only sonar-inspired market tracking and regime-risk analysis",
    )
    root = parser.add_subparsers(dest="area", required=True)

    sonar = root.add_parser("sonar", help="Run sonar-style market tracking")
    sonar_sub = sonar.add_subparsers(dest="action", required=True)
    track = sonar_sub.add_parser(
        "track", help="Compute multi-horizon echoes and forecast bands"
    )
    _add_common_arguments(track)
    track.add_argument(
        "--horizons",
        type=_horizons,
        default=(1, 5, 10),
        help="Comma-separated feature horizons",
    )

    regime = root.add_parser(
        "regime", help="Run distance-calibrated regime-risk analysis"
    )
    regime_sub = regime.add_subparsers(dest="action", required=True)
    report = regime_sub.add_parser(
        "report", help="Classify stable, transitional, stressed, or dislocated regimes"
    )
    _add_common_arguments(report)
    report.add_argument(
        "--horizons",
        type=_horizons,
        default=(1, 5, 10),
        help="Comma-separated feature horizons",
    )
    report.add_argument(
        "--reference-size",
        type=int,
        help="Eligible observations allocated to historical reference calibration",
    )

    research = root.add_parser(
        "research", help="Execute point-in-time walk-forward research"
    )
    research_sub = research.add_subparsers(dest="action", required=True)
    run = research_sub.add_parser(
        "run",
        help="Run chronological train, validation, embargo, and evaluation windows",
    )
    _add_common_arguments(run)
    run.add_argument(
        "--train-size", required=True, type=int, help="Training observations per window"
    )
    run.add_argument(
        "--validation-size",
        required=True,
        type=int,
        help="Validation observations per window",
    )
    run.add_argument(
        "--test-size",
        required=True,
        type=int,
        help="Evaluation observations per window",
    )
    run.add_argument(
        "--embargo-size",
        default=1,
        type=int,
        help="Observations embargoed between partitions",
    )
    run.add_argument(
        "--horizons",
        type=_horizons,
        default=(1, 5, 10),
        help="Comma-separated feature horizons",
    )

    calibration = root.add_parser(
        "calibration",
        help="Measure empirical forecast-band coverage on chronological post-cutoff outcomes",
    )
    calibration_sub = calibration.add_subparsers(dest="action", required=True)
    forecast = calibration_sub.add_parser(
        "forecast", help="Evaluate empirical forecast-band coverage"
    )
    forecast.add_argument(
        "--input",
        required=True,
        help="Local CSV or JSON input with timestamp and available_at fields",
    )
    forecast.add_argument(
        "--horizons",
        type=_horizons,
        default=(1, 5, 10),
        help="Comma-separated forecast horizons",
    )
    forecast.add_argument(
        "--research-config", help="Optional local ResearchConfig .kcfg file"
    )
    forecast.add_argument(
        "--step", default=1, type=int, help="Decision spacing in observations"
    )
    forecast.add_argument(
        "--max-decisions",
        type=int,
        help="Optional maximum number of most recent decisions",
    )
    forecast.add_argument(
        "--format",
        choices=("terminal", "json"),
        default="terminal",
        help="Output rendering format",
    )

    integrity = root.add_parser(
        "integrity", help="Audit point-in-time data access and research safeguards"
    )
    integrity_sub = integrity.add_subparsers(dest="action", required=True)
    audit = integrity_sub.add_parser(
        "audit", help="Create a reproducible integrity report"
    )
    _add_common_arguments(audit)
    audit.add_argument(
        "--minimum-points",
        default=4,
        type=int,
        help="Minimum eligible observation requirement",
    )

    dynamics = root.add_parser(
        "dynamics",
        help="Run marine-physics inspired volatility and market-structure tools",
    )
    dynamics_sub = dynamics.add_subparsers(dest="action", required=True)
    assess = dynamics_sub.add_parser(
        "assess",
        help="Compute hydrodynamic drag, tidal current, cavitation, and buoyancy metrics",
    )
    _add_common_arguments(assess)
    assess.add_argument(
        "--reference-liquidity",
        default=0.0,
        type=float,
        help="Optional non-negative external liquidity reference",
    )
    assess.add_argument(
        "--drag-scale",
        default=1.0,
        type=float,
        help="Non-negative drag sensitivity scale",
    )
    assess.add_argument(
        "--fast-window", default=5, type=int, help="Fast tidal-current horizon"
    )
    assess.add_argument(
        "--slow-window", default=20, type=int, help="Slow tidal-current horizon"
    )

    backtest = root.add_parser(
        "backtest",
        help="Run local point-in-time calibration research without order or P&L logic",
    )
    backtest_sub = backtest.add_subparsers(dest="action", required=True)
    options = backtest_sub.add_parser(
        "options",
        help="Evaluate historical equity moves against known option implied moves",
    )
    options.add_argument(
        "--equity-input", required=True, help="Local equity CSV or JSON input"
    )
    options.add_argument(
        "--options-input", required=True, help="Local option-quote CSV or JSON input"
    )
    options.add_argument(
        "--train-size", required=True, type=int, help="Training observations per window"
    )
    options.add_argument(
        "--validation-size",
        required=True,
        type=int,
        help="Validation observations per window",
    )
    options.add_argument(
        "--holding-size",
        required=True,
        type=int,
        help="Post-cutoff observations measured for research calibration",
    )
    options.add_argument(
        "--embargo-size",
        default=1,
        type=int,
        help="Observations embargoed between research partitions",
    )
    options.add_argument(
        "--horizons",
        type=_horizons,
        default=(1, 5, 10),
        help="Comma-separated feature horizons",
    )
    options.add_argument(
        "--universe-id", help="Historical equity-and-options universe identifier"
    )
    options.add_argument(
        "--survivorship-controlled",
        action="store_true",
        help="Declare that supplied data controls historical universe membership",
    )
    options.add_argument(
        "--calendar",
        help="Optional local explicit exchange-calendar JSON or CSV for strict session and data-quality controls",
    )
    options.add_argument(
        "--max-snapshot-lag-ms",
        type=int,
        default=300000,
        help="Maximum source-publication lag when --calendar is supplied",
    )
    options.add_argument(
        "--halted-underlying",
        action="append",
        default=[],
        help="Underlying identifier declared halted for strict option-quote validation; repeat as needed",
    )
    options.add_argument(
        "--format",
        choices=("terminal", "json"),
        default="terminal",
        help="Output rendering format",
    )

    vendor = backtest_sub.add_parser(
        "vendor",
        help="Run manifest-backed point-in-time research from licensed local exports",
    )
    vendor.add_argument(
        "--manifest",
        required=True,
        help="Local JSON manifest describing licensed point-in-time exports",
    )
    vendor.add_argument(
        "--train-size", required=True, type=int, help="Training observations per window"
    )
    vendor.add_argument(
        "--validation-size",
        required=True,
        type=int,
        help="Validation observations per window",
    )
    vendor.add_argument(
        "--holding-size",
        required=True,
        type=int,
        help="Post-cutoff observations measured for research calibration",
    )
    vendor.add_argument(
        "--embargo-size",
        default=1,
        type=int,
        help="Observations embargoed between research partitions",
    )
    vendor.add_argument(
        "--horizons",
        type=_horizons,
        default=(1, 5, 10),
        help="Comma-separated feature horizons",
    )
    vendor.add_argument(
        "--underlying",
        help="Optional underlying identifier used to constrain option-chain selection",
    )
    vendor.add_argument(
        "--format",
        choices=("terminal", "json"),
        default="terminal",
        help="Output rendering format",
    )

    diagnostics = root.add_parser(
        "diagnostics",
        help="Summarize calibration fields by sector or underlying universe",
    )
    diagnostics_sub = diagnostics.add_subparsers(dest="action", required=True)
    summarize = diagnostics_sub.add_parser(
        "summarize",
        help="Aggregate local equity-options reports without performance or trade metrics",
    )
    summarize.add_argument(
        "--backtest-json",
        required=True,
        nargs="+",
        help="One or more local Kraken equity-options JSON reports",
    )
    summarize.add_argument(
        "--group-by",
        choices=("sector", "underlying_universe"),
        default="underlying_universe",
        help="Manifest label used for aggregation",
    )
    summarize.add_argument(
        "--format",
        choices=("terminal", "json"),
        default="terminal",
        help="Output rendering format",
    )
    timeslice = diagnostics_sub.add_parser(
        "timeslice",
        help="Summarize chronological calibration slices without strategy performance metrics",
    )
    timeslice.add_argument(
        "--backtest-json",
        required=True,
        nargs="+",
        help="One or more local Kraken equity-options JSON reports",
    )
    timeslice.add_argument(
        "--slice-size",
        required=True,
        type=int,
        help="Number of chronological backtest windows per diagnostic slice",
    )
    timeslice.add_argument(
        "--format",
        choices=("terminal", "json"),
        default="terminal",
        help="Output rendering format",
    )
    visualize = diagnostics_sub.add_parser(
        "visualize",
        help="Render a local PNG visualization of chronological marine-dynamics time slices",
    )
    visualize.add_argument(
        "--backtest-json",
        required=True,
        nargs="+",
        help="One or more local Kraken equity-options JSON reports",
    )
    visualize.add_argument(
        "--slice-size",
        required=True,
        type=int,
        help="Number of chronological backtest windows per diagnostic slice",
    )
    visualize.add_argument("--output", required=True, help="Local PNG output path")
    visualize.add_argument(
        "--format",
        choices=("terminal", "json"),
        default="terminal",
        help="Output rendering format",
    )

    vendor_tools = root.add_parser(
        "vendor",
        help="Normalize licensed local provider exports into Kraken’s strict point-in-time schema",
    )
    vendor_tools_sub = vendor_tools.add_subparsers(dest="action", required=True)
    normalize = vendor_tools_sub.add_parser(
        "normalize",
        help="Map a supported local provider export profile into canonical CSV inputs",
    )
    normalizer_source = normalize.add_mutually_exclusive_group(required=True)
    normalizer_source.add_argument(
        "--profile", choices=available_profiles(), help="Supported local export profile"
    )
    normalizer_source.add_argument(
        "--mapping-file",
        help="Explicit local JSON mapping file for a licensed provider export",
    )
    normalize.add_argument(
        "--equity-source", required=True, help="Local source equity CSV export"
    )
    normalize.add_argument(
        "--options-source", required=True, help="Local source option CSV export"
    )
    normalize.add_argument(
        "--output-directory",
        required=True,
        help="Local directory for normalized canonical CSV outputs",
    )
    normalize.add_argument(
        "--format",
        choices=("terminal", "json"),
        default="terminal",
        help="Output rendering format",
    )

    compare = root.add_parser(
        "compare",
        help="Compare immutable provenance from two saved Kraken research reports",
    )
    compare_source = compare.add_mutually_exclusive_group(required=True)
    compare_source.add_argument(
        "--backtest-json",
        nargs=2,
        help="Exactly two local Kraken equity-options JSON reports",
    )
    compare_source.add_argument(
        "--manifest-json",
        nargs=2,
        help="Exactly two local immutable Kraken run-manifest JSON files",
    )
    compare.add_argument(
        "--format",
        choices=("terminal", "json"),
        default="terminal",
        help="Output rendering format",
    )

    bundle = root.add_parser(
        "bundle",
        help="Create an auditable local research bundle from a saved manifest-backed report",
    )
    bundle_sub = bundle.add_subparsers(dest="action", required=True)
    create = bundle_sub.add_parser(
        "create",
        help="Write JSON, integrity evidence, config, provenance, disclosures, and optional local artifacts",
    )
    create.add_argument(
        "--backtest-json",
        required=True,
        help="Local Kraken equity-options JSON report containing an immutable manifest",
    )
    create.add_argument(
        "--config", required=True, help="Canonical local ResearchConfig .kcfg file"
    )
    create.add_argument(
        "--output-directory",
        required=True,
        help="Empty local directory for the auditable bundle",
    )
    create.add_argument(
        "--chart", help="Optional local chart artifact to copy into the bundle"
    )
    create.add_argument(
        "--benchmark-context",
        help="Optional local benchmark or comparison JSON to copy into the bundle",
    )
    create.add_argument(
        "--format",
        choices=("terminal", "json"),
        default="terminal",
        help="Output rendering format",
    )
    return parser


def _terminal(value: Any, indent: int = 0) -> str:
    primitive = to_primitive(value)
    if isinstance(primitive, dict):
        lines: list[str] = []
        for key, item in primitive.items():
            label = key.replace("_", " ").upper()
            if isinstance(item, (dict, list)):
                lines.append(f"{'  ' * indent}{label}")
                lines.append(_terminal(item, indent + 1))
            else:
                lines.append(f"{'  ' * indent}{label}: {item}")
        return "\n".join(lines)
    if isinstance(primitive, list):
        if not primitive:
            return f"{'  ' * indent}NONE"
        lines = []
        for index, item in enumerate(primitive, 1):
            lines.append(f"{'  ' * indent}[{index}]")
            lines.append(_terminal(item, indent + 1))
        return "\n".join(lines)
    return f"{'  ' * indent}{primitive}"


def _emit(value: Any, output_format: str) -> None:
    primitive = to_primitive(value)
    if output_format == "json":
        print(json.dumps(primitive, sort_keys=True, indent=2))
    else:
        print("KRAKEN RESEARCH OUTPUT")
        print("Research-only. Not trading instructions.")
        print(_terminal(primitive))


def execute(args: argparse.Namespace) -> Any:
    if args.area == "bundle" and args.action == "create":
        config_path = Path(args.config).expanduser().resolve()
        if not config_path.is_file():
            raise ValueError("Bundle configuration file does not exist")
        return create_research_bundle(
            load_backtest_report(args.backtest_json),
            args.output_directory,
            config_path.read_text(encoding="utf-8"),
            chart_path=args.chart,
            benchmark_context_path=args.benchmark_context,
        )
    if args.area == "compare":
        if args.manifest_json:
            left, right = (load_run_manifest(path) for path in args.manifest_json)
            return compare_run_manifests(left, right)
        left, right = (load_backtest_report(path) for path in args.backtest_json)
        if left.manifest is None or right.manifest is None:
            raise ValueError("Both research reports must contain immutable manifests")
        return compare_run_manifests(left.manifest, right.manifest)
    if args.area == "calibration" and args.action == "forecast":
        observations = load_observations(args.input)
        config = (
            Path(args.research_config)
            .expanduser()
            .resolve()
            .read_text(encoding="utf-8")
            if args.research_config
            else None
        )
        return calibrate_forecast_bands(
            observations,
            horizons=args.horizons,
            research_config=config,
            step=args.step,
            max_decisions=args.max_decisions,
        )
    if args.area == "vendor" and args.action == "normalize":
        return normalize_provider_exports(
            args.profile or "mapping_file",
            args.equity_source,
            args.options_source,
            args.output_directory,
            mapping_file=args.mapping_file,
        )
    if args.area == "diagnostics" and args.action == "summarize":
        return calibration_diagnostics(
            (load_backtest_report(path) for path in args.backtest_json),
            group_by=args.group_by,
        )
    if args.area == "diagnostics" and args.action == "timeslice":
        return time_sliced_calibration_diagnostics(
            (load_backtest_report(path) for path in args.backtest_json),
            slice_size=args.slice_size,
        )
    if args.area == "diagnostics" and args.action == "visualize":
        report = time_sliced_calibration_diagnostics(
            (load_backtest_report(path) for path in args.backtest_json),
            slice_size=args.slice_size,
        )
        return render_time_sliced_diagnostics(report, args.output)
    if args.area == "backtest" and args.action == "options":
        return run_equity_options_backtest(
            load_observations(args.equity_input),
            load_option_quotes(args.options_input),
            train_size=args.train_size,
            validation_size=args.validation_size,
            holding_size=args.holding_size,
            embargo_size=args.embargo_size,
            horizons=args.horizons,
            universe_id=args.universe_id,
            survivorship_controlled=args.survivorship_controlled,
            exchange_sessions=(
                load_exchange_calendar(args.calendar) if args.calendar else None
            ),
            data_quality_policy=MarketDataQualityPolicy(
                max_snapshot_lag_ms=args.max_snapshot_lag_ms
            ),
            halted_underlyings=args.halted_underlying,
        )
    if args.area == "backtest" and args.action == "vendor":
        return run_vendor_equity_options_backtest(
            args.manifest,
            train_size=args.train_size,
            validation_size=args.validation_size,
            holding_size=args.holding_size,
            embargo_size=args.embargo_size,
            horizons=args.horizons,
            underlying=args.underlying,
        )
    observations = load_observations(args.input)
    cutoff = _cutoff(args.cutoff, observations)
    if args.area == "sonar" and args.action == "track":
        return run_sonar_tracker(
            observations,
            cutoff,
            horizons=args.horizons,
            universe_id=args.universe_id,
            survivorship_controlled=args.survivorship_controlled,
        )
    if args.area == "regime" and args.action == "report":
        return analyze_regime_risk(
            observations,
            cutoff,
            horizons=args.horizons,
            reference_size=args.reference_size,
            universe_id=args.universe_id,
            survivorship_controlled=args.survivorship_controlled,
        )
    if args.area == "research" and args.action == "run":
        return run_walk_forward(
            observations,
            train_size=args.train_size,
            validation_size=args.validation_size,
            test_size=args.test_size,
            embargo_size=args.embargo_size,
            horizons=args.horizons,
            universe_id=args.universe_id,
            survivorship_controlled=args.survivorship_controlled,
        )
    if args.area == "integrity" and args.action == "audit":
        return build_integrity_audit(
            observations,
            cutoff,
            {"analysis": "integrity_audit", "minimum_points": args.minimum_points},
            minimum_points=args.minimum_points,
            universe_id=args.universe_id,
            survivorship_controlled=args.survivorship_controlled,
        )
    if args.area == "dynamics" and args.action == "assess":
        return analyze_marine_dynamics(
            observations,
            cutoff,
            reference_liquidity=args.reference_liquidity,
            drag_scale=args.drag_scale,
            fast_window=args.fast_window,
            slow_window=args.slow_window,
            universe_id=args.universe_id,
            survivorship_controlled=args.survivorship_controlled,
        )
    raise ValueError("Unsupported command")


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        _emit(execute(args), args.format)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        parser.exit(2, f"kraken: error: {exc}\n")


if __name__ == "__main__":
    main(sys.argv[1:])
