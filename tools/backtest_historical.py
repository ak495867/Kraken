import argparse
import json

from kraken import (
    load_observations,
    load_option_quotes,
    run_equity_options_backtest,
    run_vendor_equity_options_backtest,
)
from kraken.models import to_primitive


def parse_horizons(value: str) -> tuple[int, ...]:
    parsed = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    if not parsed or any(item <= 0 for item in parsed):
        raise argparse.ArgumentTypeError(
            "Horizons must be comma-separated positive integers"
        )
    return parsed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Local point-in-time equity-options calibration research backtest"
    )
    parser.add_argument("--equity-input")
    parser.add_argument("--options-input")
    parser.add_argument("--manifest")
    parser.add_argument("--train-size", required=True, type=int)
    parser.add_argument("--validation-size", required=True, type=int)
    parser.add_argument("--holding-size", required=True, type=int)
    parser.add_argument("--embargo-size", default=1, type=int)
    parser.add_argument("--horizons", type=parse_horizons, default=(1, 5, 10))
    parser.add_argument("--universe-id")
    parser.add_argument("--survivorship-controlled", action="store_true")
    parser.add_argument("--output")
    args = parser.parse_args()
    if args.manifest:
        report = run_vendor_equity_options_backtest(
            args.manifest,
            train_size=args.train_size,
            validation_size=args.validation_size,
            holding_size=args.holding_size,
            embargo_size=args.embargo_size,
            horizons=args.horizons,
        )
    else:
        if not args.equity_input or not args.options_input:
            parser.error(
                "--equity-input and --options-input are required when --manifest is not supplied"
            )
        report = run_equity_options_backtest(
            load_observations(args.equity_input),
            load_option_quotes(args.options_input),
            train_size=args.train_size,
            validation_size=args.validation_size,
            holding_size=args.holding_size,
            embargo_size=args.embargo_size,
            horizons=args.horizons,
            universe_id=args.universe_id,
            survivorship_controlled=args.survivorship_controlled,
        )
    payload = json.dumps(to_primitive(report), sort_keys=True, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(payload + "\n")
    else:
        print(payload)


if __name__ == "__main__":
    main()
