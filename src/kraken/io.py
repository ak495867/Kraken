from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import CorporateAction, DistributionRecord, EarningsEvent, LicensedVendorManifest, Observation, OptionContractAdjustment, OptionQuote


REQUIRED_FIELDS = (
    "timestamp",
    "available_at",
    "close",
    "volume",
    "realized_volatility",
    "liquidity",
)

OPTION_REQUIRED_FIELDS = (
    "timestamp",
    "available_at",
    "expiration",
    "contract",
    "option_type",
    "strike",
    "bid",
    "ask",
    "implied_volatility",
    "open_interest",
    "volume",
    "underlying",
)

CORPORATE_ACTION_REQUIRED_FIELDS = (
    "effective_at",
    "available_at",
    "underlying",
    "action_type",
    "factor",
)

OPTION_ADJUSTMENT_REQUIRED_FIELDS = (
    "effective_at",
    "available_at",
    "underlying",
    "pre_contract",
    "post_contract",
    "strike_factor",
    "multiplier_factor",
)

DISTRIBUTION_REQUIRED_FIELDS = (
    "effective_at",
    "available_at",
    "underlying",
    "distribution_type",
    "amount",
)

EARNINGS_REQUIRED_FIELDS = (
    "event_at",
    "available_at",
    "underlying",
    "fiscal_period",
    "event_type",
)


def parse_timestamp(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("Timestamp values must be UTC ISO-8601 strings or Unix milliseconds")
    if isinstance(value, (int, float)):
        if not math.isfinite(float(value)) or int(value) <= 0:
            raise ValueError("Unix millisecond timestamps must be positive finite values")
        return int(value)
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Timestamp values must be UTC ISO-8601 strings or Unix milliseconds")
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"Invalid timestamp: {value}") from exc
    if parsed.tzinfo is None:
        raise ValueError("ISO-8601 timestamps must include an explicit UTC offset")
    return int(parsed.astimezone(timezone.utc).timestamp() * 1000)


def _parse_number(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a finite numeric value")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a finite numeric value") from exc
    if not math.isfinite(parsed):
        raise ValueError(f"{field} must be a finite numeric value")
    return parsed


def observation_from_mapping(row: dict[str, Any], row_number: int) -> Observation:
    missing = [field for field in REQUIRED_FIELDS if field not in row or row[field] in (None, "")]
    if missing:
        raise ValueError(f"Row {row_number} is missing required fields: {', '.join(missing)}")
    observation = Observation(
        timestamp_ms=parse_timestamp(row["timestamp"]),
        available_at_ms=parse_timestamp(row["available_at"]),
        close=_parse_number(row["close"], "close"),
        volume=_parse_number(row["volume"], "volume"),
        realized_volatility=_parse_number(row["realized_volatility"], "realized_volatility"),
        liquidity=_parse_number(row["liquidity"], "liquidity"),
    )
    if observation.close <= 0.0:
        raise ValueError(f"Row {row_number} has a non-positive close")
    if observation.volume < 0.0 or observation.realized_volatility < 0.0 or observation.liquidity < 0.0:
        raise ValueError(f"Row {row_number} has a negative volume, realized_volatility, or liquidity")
    if observation.available_at_ms < observation.timestamp_ms:
        raise ValueError(f"Row {row_number} has available_at earlier than timestamp")
    return observation


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("CSV input must include a header row")
        return [dict(row) for row in reader]


def _read_json(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, dict):
        payload = payload.get("observations")
    if not isinstance(payload, list):
        raise ValueError("JSON input must be an array or an object with an observations array")
    if not all(isinstance(row, dict) for row in payload):
        raise ValueError("JSON observations must be objects")
    return payload


def load_observations(path: str | Path) -> tuple[Observation, ...]:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise ValueError(f"Input file does not exist: {source}")
    if source.suffix.lower() == ".csv":
        rows = _read_csv(source)
    elif source.suffix.lower() == ".json":
        rows = _read_json(source)
    else:
        raise ValueError("Input must be a .csv or .json file")
    if not rows:
        raise ValueError("Input data must contain at least one observation")
    observations = tuple(observation_from_mapping(row, index + 2) for index, row in enumerate(rows))
    if any(observations[index].timestamp_ms <= observations[index - 1].timestamp_ms for index in range(1, len(observations))):
        raise ValueError("Observation timestamps must be strictly increasing")
    return observations


def option_quote_from_mapping(row: dict[str, Any], row_number: int) -> OptionQuote:
    missing = [field for field in OPTION_REQUIRED_FIELDS if field not in row or row[field] in (None, "")]
    if missing:
        raise ValueError(f"Option row {row_number} is missing required fields: {', '.join(missing)}")
    option_type = str(row["option_type"]).strip().lower()
    quote = OptionQuote(
        timestamp_ms=parse_timestamp(row["timestamp"]),
        available_at_ms=parse_timestamp(row["available_at"]),
        expiration_ms=parse_timestamp(row["expiration"]),
        contract=str(row["contract"]).strip(),
        option_type=option_type,
        strike=_parse_number(row["strike"], "strike"),
        bid=_parse_number(row["bid"], "bid"),
        ask=_parse_number(row["ask"], "ask"),
        implied_volatility=_parse_number(row["implied_volatility"], "implied_volatility"),
        open_interest=_parse_number(row["open_interest"], "open_interest"),
        volume=_parse_number(row["volume"], "volume"),
        underlying=str(row["underlying"]).strip(),
    )
    if not quote.contract or not quote.underlying:
        raise ValueError(f"Option row {row_number} has an empty contract or underlying")
    if quote.option_type not in {"call", "put"}:
        raise ValueError(f"Option row {row_number} option_type must be call or put")
    if quote.available_at_ms < quote.timestamp_ms:
        raise ValueError(f"Option row {row_number} has available_at earlier than timestamp")
    if quote.expiration_ms <= quote.timestamp_ms:
        raise ValueError(f"Option row {row_number} expiration must be after timestamp")
    if quote.strike <= 0.0 or quote.bid < 0.0 or quote.ask < quote.bid or quote.implied_volatility < 0.0 or quote.open_interest < 0.0 or quote.volume < 0.0:
        raise ValueError(f"Option row {row_number} has an invalid quote value")
    return quote


def load_option_quotes(path: str | Path) -> tuple[OptionQuote, ...]:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise ValueError(f"Option input file does not exist: {source}")
    if source.suffix.lower() == ".csv":
        rows = _read_csv(source)
    elif source.suffix.lower() == ".json":
        rows = _read_json(source)
    else:
        raise ValueError("Option input must be a .csv or .json file")
    if not rows:
        raise ValueError("Option input must contain at least one quote")
    quotes = tuple(option_quote_from_mapping(row, index + 2) for index, row in enumerate(rows))
    if any(quotes[index].timestamp_ms < quotes[index - 1].timestamp_ms for index in range(1, len(quotes))):
        raise ValueError("Option quote timestamps must be non-decreasing")
    return quotes


def _load_rows(path: str | Path, label: str) -> list[dict[str, Any]]:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise ValueError(f"{label} file does not exist: {source}")
    if source.suffix.lower() == ".csv":
        rows = _read_csv(source)
    elif source.suffix.lower() == ".json":
        rows = _read_json(source)
    else:
        raise ValueError(f"{label} input must be a .csv or .json file")
    if not rows:
        raise ValueError(f"{label} input must contain at least one record")
    return rows


def corporate_action_from_mapping(row: dict[str, Any], row_number: int) -> CorporateAction:
    missing = [field for field in CORPORATE_ACTION_REQUIRED_FIELDS if field not in row or row[field] in (None, "")]
    if missing:
        raise ValueError(f"Corporate-action row {row_number} is missing required fields: {', '.join(missing)}")
    action = CorporateAction(
        effective_at_ms=parse_timestamp(row["effective_at"]),
        available_at_ms=parse_timestamp(row["available_at"]),
        underlying=str(row["underlying"]).strip(),
        action_type=str(row["action_type"]).strip().lower(),
        factor=_parse_number(row["factor"], "factor"),
    )
    if not action.underlying:
        raise ValueError(f"Corporate-action row {row_number} has an empty underlying")
    if action.action_type not in {"stock_split", "reverse_split"}:
        raise ValueError(f"Corporate-action row {row_number} action_type must be stock_split or reverse_split")
    if action.factor <= 0.0:
        raise ValueError(f"Corporate-action row {row_number} factor must be positive")
    return action


def option_adjustment_from_mapping(row: dict[str, Any], row_number: int) -> OptionContractAdjustment:
    missing = [field for field in OPTION_ADJUSTMENT_REQUIRED_FIELDS if field not in row or row[field] in (None, "")]
    if missing:
        raise ValueError(f"Option-adjustment row {row_number} is missing required fields: {', '.join(missing)}")
    adjustment = OptionContractAdjustment(
        effective_at_ms=parse_timestamp(row["effective_at"]),
        available_at_ms=parse_timestamp(row["available_at"]),
        underlying=str(row["underlying"]).strip(),
        pre_contract=str(row["pre_contract"]).strip(),
        post_contract=str(row["post_contract"]).strip(),
        strike_factor=_parse_number(row["strike_factor"], "strike_factor"),
        multiplier_factor=_parse_number(row["multiplier_factor"], "multiplier_factor"),
    )
    if not adjustment.underlying or not adjustment.pre_contract or not adjustment.post_contract:
        raise ValueError(f"Option-adjustment row {row_number} has an empty identifier")
    if adjustment.strike_factor <= 0.0 or adjustment.multiplier_factor <= 0.0:
        raise ValueError(f"Option-adjustment row {row_number} factors must be positive")
    return adjustment


def load_corporate_actions(path: str | Path) -> tuple[CorporateAction, ...]:
    rows = _load_rows(path, "Corporate-action")
    actions = tuple(corporate_action_from_mapping(row, index + 2) for index, row in enumerate(rows))
    if any(actions[index].effective_at_ms < actions[index - 1].effective_at_ms for index in range(1, len(actions))):
        raise ValueError("Corporate-action effective timestamps must be non-decreasing")
    return actions


def load_option_adjustments(path: str | Path) -> tuple[OptionContractAdjustment, ...]:
    rows = _load_rows(path, "Option-adjustment")
    adjustments = tuple(option_adjustment_from_mapping(row, index + 2) for index, row in enumerate(rows))
    if any(adjustments[index].effective_at_ms < adjustments[index - 1].effective_at_ms for index in range(1, len(adjustments))):
        raise ValueError("Option-adjustment effective timestamps must be non-decreasing")
    return adjustments


def distribution_from_mapping(row: dict[str, Any], row_number: int) -> DistributionRecord:
    missing = [field for field in DISTRIBUTION_REQUIRED_FIELDS if field not in row or row[field] in (None, "")]
    if missing:
        raise ValueError(f"Distribution row {row_number} is missing required fields: {', '.join(missing)}")
    distribution = DistributionRecord(
        effective_at_ms=parse_timestamp(row["effective_at"]),
        available_at_ms=parse_timestamp(row["available_at"]),
        underlying=str(row["underlying"]).strip(),
        distribution_type=str(row["distribution_type"]).strip().lower(),
        amount=_parse_number(row["amount"], "amount"),
    )
    if not distribution.underlying:
        raise ValueError(f"Distribution row {row_number} has an empty underlying")
    if distribution.distribution_type not in {"cash_dividend", "special_distribution"}:
        raise ValueError(f"Distribution row {row_number} distribution_type must be cash_dividend or special_distribution")
    if distribution.amount <= 0.0:
        raise ValueError(f"Distribution row {row_number} amount must be positive")
    return distribution


def load_distributions(path: str | Path) -> tuple[DistributionRecord, ...]:
    rows = _load_rows(path, "Distribution")
    distributions = tuple(distribution_from_mapping(row, index + 2) for index, row in enumerate(rows))
    if any(distributions[index].effective_at_ms < distributions[index - 1].effective_at_ms for index in range(1, len(distributions))):
        raise ValueError("Distribution effective timestamps must be non-decreasing")
    return distributions


def earnings_event_from_mapping(row: dict[str, Any], row_number: int) -> EarningsEvent:
    missing = [field for field in EARNINGS_REQUIRED_FIELDS if field not in row or row[field] in (None, "")]
    if missing:
        raise ValueError(f"Earnings row {row_number} is missing required fields: {', '.join(missing)}")
    event = EarningsEvent(
        event_at_ms=parse_timestamp(row["event_at"]),
        available_at_ms=parse_timestamp(row["available_at"]),
        underlying=str(row["underlying"]).strip(),
        fiscal_period=str(row["fiscal_period"]).strip(),
        event_type=str(row["event_type"]).strip().lower(),
    )
    if not event.underlying or not event.fiscal_period:
        raise ValueError(f"Earnings row {row_number} has an empty underlying or fiscal_period")
    if event.event_type not in {"earnings_release", "guidance_update", "earnings_revision"}:
        raise ValueError(f"Earnings row {row_number} event_type is not supported")
    return event


def load_earnings_events(path: str | Path) -> tuple[EarningsEvent, ...]:
    rows = _load_rows(path, "Earnings")
    events = tuple(earnings_event_from_mapping(row, index + 2) for index, row in enumerate(rows))
    if any(events[index].event_at_ms < events[index - 1].event_at_ms for index in range(1, len(events))):
        raise ValueError("Earnings event timestamps must be non-decreasing")
    return events


def load_vendor_manifest(path: str | Path) -> LicensedVendorManifest:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise ValueError(f"Vendor manifest file does not exist: {source}")
    with source.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("Vendor manifest must be a JSON object")
    required = ("provider", "dataset_id", "snapshot_as_of", "price_basis", "equity_path", "options_path")
    missing = [field for field in required if field not in payload or payload[field] in (None, "")]
    if missing:
        raise ValueError(f"Vendor manifest is missing required fields: {', '.join(missing)}")
    price_basis = str(payload["price_basis"]).strip().lower()
    if price_basis not in {"raw", "split_adjusted"}:
        raise ValueError("Vendor manifest price_basis must be raw or split_adjusted")
    def resolve_reference(value: Any) -> str | None:
        if value in (None, ""):
            return None
        return str((source.parent / str(value)).resolve())
    manifest = LicensedVendorManifest(
        provider=str(payload["provider"]).strip(),
        dataset_id=str(payload["dataset_id"]).strip(),
        snapshot_as_of_ms=parse_timestamp(payload["snapshot_as_of"]),
        price_basis=price_basis,
        equity_path=resolve_reference(payload["equity_path"]) or "",
        options_path=resolve_reference(payload["options_path"]) or "",
        corporate_actions_path=resolve_reference(payload.get("corporate_actions_path")),
        option_adjustments_path=resolve_reference(payload.get("option_adjustments_path")),
        distributions_path=resolve_reference(payload.get("distributions_path")),
        earnings_path=resolve_reference(payload.get("earnings_path")),
        sector=str(payload["sector"]).strip() if payload.get("sector") not in (None, "") else None,
        underlying_universe=str(payload["underlying_universe"]).strip() if payload.get("underlying_universe") not in (None, "") else None,
        normalizer_profile=str(payload["normalizer_profile"]).strip() if payload.get("normalizer_profile") not in (None, "") else None,
        mapping_path=resolve_reference(payload.get("mapping_path")),
    )
    if not manifest.provider or not manifest.dataset_id:
        raise ValueError("Vendor manifest provider and dataset_id must be non-empty")
    return manifest
