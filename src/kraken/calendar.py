from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

from .models import (
    ExchangeSession,
    IntegrityIssue,
    MarketDataQualityPolicy,
    MarketDataQualityReport,
    Observation,
    OptionQuote,
)


def _session_date(timestamp_ms: int) -> str:
    return (
        datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).date().isoformat()
    )


def _issue(policy: MarketDataQualityPolicy, code: str, message: str) -> IntegrityIssue:
    return IntegrityIssue(
        code=code, severity="error" if policy.strict else "warning", message=message
    )


def load_exchange_calendar(path: str | Path) -> tuple[ExchangeSession, ...]:
    source = Path(path)
    if not source.is_file():
        raise ValueError(f"Exchange calendar does not exist: {source}")
    if source.suffix.lower() == ".json":
        loaded = json.loads(source.read_text(encoding="utf-8"))
        rows = loaded["sessions"] if isinstance(loaded, dict) else loaded
    elif source.suffix.lower() == ".csv":
        with source.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
    else:
        raise ValueError("Exchange calendar must use .json or .csv")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Exchange calendar must contain a non-empty session list")
    sessions: list[ExchangeSession] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Every exchange calendar session must be an object")
        try:
            session = ExchangeSession(
                session_date=str(row["session_date"]),
                open_ms=int(row["open_ms"]),
                close_ms=int(row["close_ms"]),
                is_half_day=str(row.get("is_half_day", "false")).lower()
                in {"1", "true", "yes"},
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                "Exchange calendar sessions require session_date, open_ms, and close_ms"
            ) from exc
        if session.open_ms >= session.close_ms:
            raise ValueError(
                f"Exchange calendar session has non-positive duration: {session.session_date}"
            )
        sessions.append(session)
    ordered = tuple(sorted(sessions, key=lambda item: item.session_date))
    if len({item.session_date for item in ordered}) != len(ordered):
        raise ValueError("Exchange calendar has duplicate session_date values")
    return ordered


def validate_market_data_quality(
    observations: Sequence[Observation],
    option_quotes: Sequence[OptionQuote],
    decision_cutoff_ms: int,
    sessions: Sequence[ExchangeSession],
    policy: MarketDataQualityPolicy | None = None,
    halted_underlyings: Iterable[str] = (),
) -> MarketDataQualityReport:
    active_policy = policy or MarketDataQualityPolicy()
    if active_policy.max_snapshot_lag_ms < 0:
        raise ValueError("max_snapshot_lag_ms must be non-negative")
    if active_policy.minimum_option_strikes < 1:
        raise ValueError("minimum_option_strikes must be at least one")
    session_by_date = {item.session_date: item for item in sessions}
    if not session_by_date:
        raise ValueError("At least one explicit exchange session is required")
    if len(session_by_date) != len(sessions):
        raise ValueError("Exchange calendar has duplicate session_date values")
    issues: list[IntegrityIssue] = []
    warnings: list[str] = []
    duplicate_snapshot_count = 0
    stale_snapshot_count = 0
    incomplete_option_chain_count = 0
    halted = frozenset(halted_underlyings)
    observation_keys: set[tuple[int, int]] = set()
    observed_dates: set[str] = set()
    for observation in observations:
        date = _session_date(observation.timestamp_ms)
        observed_dates.add(date)
        session = session_by_date.get(date)
        if session is None:
            issues.append(
                _issue(
                    active_policy,
                    "calendar_session_missing",
                    f"Observation timestamp {observation.timestamp_ms} is not on an explicit exchange session",
                )
            )
        elif not session.open_ms <= observation.timestamp_ms <= session.close_ms:
            issues.append(
                _issue(
                    active_policy,
                    "outside_exchange_session",
                    f"Observation timestamp {observation.timestamp_ms} falls outside the declared {date} trading session",
                )
            )
        key = (observation.timestamp_ms, observation.available_at_ms)
        if key in observation_keys:
            duplicate_snapshot_count += 1
            issues.append(
                _issue(
                    active_policy,
                    "duplicate_observation_snapshot",
                    f"Duplicate observation snapshot at timestamp {observation.timestamp_ms}",
                )
            )
        observation_keys.add(key)
        lag = observation.available_at_ms - observation.timestamp_ms
        if lag > active_policy.max_snapshot_lag_ms:
            stale_snapshot_count += 1
            issues.append(
                _issue(
                    active_policy,
                    "stale_observation_snapshot",
                    f"Observation at {observation.timestamp_ms} was published {lag} ms after its timestamp",
                )
            )
    ordered_dates = tuple(sorted(observed_dates))
    if len(ordered_dates) > 1:
        expected_dates = tuple(
            item.session_date
            for item in sessions
            if ordered_dates[0] <= item.session_date <= ordered_dates[-1]
        )
        missing = tuple(date for date in expected_dates if date not in observed_dates)
        if missing:
            warnings.append(
                f"Observation history omits {len(missing)} explicit exchange session(s) between its first and last observed date"
            )
    option_keys: set[tuple[str, str, int, int]] = set()
    chain_quotes: dict[tuple[str, int, int], list[OptionQuote]] = defaultdict(list)
    for quote in option_quotes:
        if quote.available_at_ms > decision_cutoff_ms:
            continue
        date = _session_date(quote.timestamp_ms)
        session = session_by_date.get(date)
        if session is None:
            issues.append(
                _issue(
                    active_policy,
                    "option_calendar_session_missing",
                    f"Option quote {quote.contract} is not on an explicit exchange session",
                )
            )
        elif not session.open_ms <= quote.timestamp_ms <= session.close_ms:
            issues.append(
                _issue(
                    active_policy,
                    "option_outside_exchange_session",
                    f"Option quote {quote.contract} falls outside the declared {date} trading session",
                )
            )
        key = (
            quote.contract,
            quote.option_type,
            quote.timestamp_ms,
            quote.available_at_ms,
        )
        if key in option_keys:
            duplicate_snapshot_count += 1
            issues.append(
                _issue(
                    active_policy,
                    "duplicate_option_snapshot",
                    f"Duplicate option snapshot for {quote.contract} at {quote.timestamp_ms}",
                )
            )
        option_keys.add(key)
        lag = quote.available_at_ms - quote.timestamp_ms
        if lag > active_policy.max_snapshot_lag_ms:
            stale_snapshot_count += 1
            issues.append(
                _issue(
                    active_policy,
                    "stale_option_snapshot",
                    f"Option quote {quote.contract} was published {lag} ms after its timestamp",
                )
            )
        if quote.underlying in halted:
            issues.append(
                _issue(
                    active_policy,
                    "halted_underlying_quote",
                    f"Option quote {quote.contract} references halted underlying {quote.underlying}",
                )
            )
        chain_quotes[
            (quote.underlying, quote.timestamp_ms, quote.expiration_ms)
        ].append(quote)
    for key, quotes in chain_quotes.items():
        types = {item.option_type.lower() for item in quotes}
        strikes = {item.strike for item in quotes}
        reasons: list[str] = []
        if active_policy.require_calls_and_puts and not {"call", "put"}.issubset(types):
            reasons.append("both call and put quotes")
        if len(strikes) < active_policy.minimum_option_strikes:
            reasons.append(f"at least {active_policy.minimum_option_strikes} strike(s)")
        if reasons:
            incomplete_option_chain_count += 1
            issues.append(
                _issue(
                    active_policy,
                    "incomplete_option_chain",
                    f"Option chain {key[0]} at {key[1]} requires {' and '.join(reasons)}",
                )
            )
    valid = not any(item.severity == "error" for item in issues)
    return MarketDataQualityReport(
        valid=valid,
        decision_cutoff_ms=decision_cutoff_ms,
        calendar_session_count=len(sessions),
        checked_observation_count=len(observations),
        checked_option_quote_count=sum(
            1 for quote in option_quotes if quote.available_at_ms <= decision_cutoff_ms
        ),
        duplicate_snapshot_count=duplicate_snapshot_count,
        stale_snapshot_count=stale_snapshot_count,
        incomplete_option_chain_count=incomplete_option_chain_count,
        warnings=tuple(warnings),
        issues=tuple(issues),
    )
