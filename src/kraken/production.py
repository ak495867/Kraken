from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Protocol

from .io import parse_timestamp
from .models import Observation


class ObservationSource(Protocol):
    def fetch(self) -> Iterable[Observation]: ...


class AlertSink(Protocol):
    def emit(self, level: str, event: str, payload: dict[str, Any]) -> None: ...


@dataclass(frozen=True)
class RetryPolicy:
    attempts: int = 3
    base_delay_seconds: float = 0.5
    max_delay_seconds: float = 30.0

    def validate(self) -> None:
        if self.attempts < 1:
            raise ValueError("Retry attempts must be positive")
        if (
            self.base_delay_seconds < 0
            or self.max_delay_seconds < self.base_delay_seconds
        ):
            raise ValueError("Retry delay bounds are invalid")


@dataclass(frozen=True)
class IngestionPolicy:
    max_clock_skew_ms: int = 300000
    max_batch_size: int = 100000
    require_strict_chronology: bool = True

    def validate(self) -> None:
        if self.max_clock_skew_ms < 0:
            raise ValueError("Maximum clock skew must be non-negative")
        if self.max_batch_size < 1:
            raise ValueError("Maximum batch size must be positive")


@dataclass(frozen=True)
class ServiceHealth:
    name: str
    status: str
    last_success_ms: int | None = None
    last_failure_ms: int | None = None
    consecutive_failures: int = 0
    last_error: str | None = None


@dataclass
class RuntimeMetrics:
    counters: dict[str, int] = field(default_factory=dict)
    gauges: dict[str, float] = field(default_factory=dict)

    def increment(self, name: str, amount: int = 1) -> None:
        self.counters[name] = self.counters.get(name, 0) + amount

    def set_gauge(self, name: str, value: float) -> None:
        self.gauges[name] = value

    def prometheus(self) -> str:
        lines = []
        for name, value in sorted(self.counters.items()):
            lines.append(f"kraken_{name} {value}")
        for name, value in sorted(self.gauges.items()):
            lines.append(f"kraken_{name} {value}")
        return "\n".join(lines) + "\n"


class JsonlAlertSink:
    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def emit(self, level: str, event: str, payload: dict[str, Any]) -> None:
        record = {
            "level": level,
            "event": event,
            "timestamp_ms": int(time.time() * 1000),
            "payload": payload,
        }
        with self._lock:
            with self.path.open("a", encoding="utf-8") as target:
                target.write(json.dumps(record, sort_keys=True) + "\n")


class HttpJsonAlertSink:
    def __init__(
        self,
        url: str,
        token_env: str,
        timeout_seconds: float = 10.0,
        opener: Callable[..., Any] | None = None,
    ):
        if not url.startswith("https://"):
            raise ValueError("Alert URL must use HTTPS")
        if timeout_seconds <= 0:
            raise ValueError("Alert timeout must be positive")
        self.url = url
        self.token_env = token_env
        self.timeout_seconds = timeout_seconds
        self.opener = opener or urllib.request.urlopen
        self.secrets = EnvironmentSecretStore()

    def emit(self, level: str, event: str, payload: dict[str, Any]) -> None:
        body = json.dumps(
            {
                "level": level,
                "event": event,
                "timestamp_ms": int(time.time() * 1000),
                "payload": payload,
            },
            sort_keys=True,
        ).encode("utf-8")
        request = urllib.request.Request(
            self.url,
            data=body,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.secrets.require(self.token_env)}",
            },
            method="POST",
        )
        with self.opener(request, timeout=self.timeout_seconds) as response:
            if response.status < 200 or response.status >= 300:
                raise RuntimeError("Alert endpoint rejected the notification")


class CompositeAlertSink:
    def __init__(self, *sinks: AlertSink):
        if not sinks:
            raise ValueError("Composite alert sink requires at least one sink")
        self.sinks = sinks

    def emit(self, level: str, event: str, payload: dict[str, Any]) -> None:
        for sink in self.sinks:
            sink.emit(level, event, payload)


class EnvironmentSecretStore:
    def require(self, name: str) -> str:
        value = os.environ.get(name)
        if not value:
            raise RuntimeError(f"Required secret {name} is not configured")
        return value


class HttpJsonObservationSource:
    def __init__(
        self,
        url: str,
        token_env: str | None = None,
        timeout_seconds: float = 10.0,
        opener: Callable[..., Any] | None = None,
    ):
        if not url.startswith(("https://", "http://")):
            raise ValueError("Observation source URL must use HTTP or HTTPS")
        if timeout_seconds <= 0:
            raise ValueError("HTTP timeout must be positive")
        self.url = url
        self.token_env = token_env
        self.timeout_seconds = timeout_seconds
        self.opener = opener or urllib.request.urlopen
        self.secrets = EnvironmentSecretStore()

    def fetch(self) -> tuple[Observation, ...]:
        headers = {"Accept": "application/json"}
        if self.token_env:
            headers["Authorization"] = f"Bearer {self.secrets.require(self.token_env)}"
        request = urllib.request.Request(self.url, headers=headers, method="GET")
        with self.opener(request, timeout=self.timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
        rows = payload.get("observations") if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            raise ValueError(
                "Observation endpoint must return a list or an observations list"
            )
        return tuple(observation_from_mapping(row) for row in rows)


def observation_from_mapping(row: dict[str, Any]) -> Observation:
    if not isinstance(row, dict):
        raise ValueError("Observation rows must be objects")
    return Observation(
        timestamp_ms=parse_timestamp(row["timestamp"]),
        available_at_ms=parse_timestamp(row["available_at"]),
        close=float(row["close"]),
        volume=float(row["volume"]),
        realized_volatility=float(row["realized_volatility"]),
        liquidity=float(row["liquidity"]),
    )


def validate_ingestion_batch(
    observations: Iterable[Observation],
    policy: IngestionPolicy,
    now_ms: int | None = None,
) -> tuple[Observation, ...]:
    policy.validate()
    batch = tuple(observations)
    if not batch:
        raise ValueError("Observation ingestion batch cannot be empty")
    if len(batch) > policy.max_batch_size:
        raise ValueError("Observation ingestion batch exceeds configured maximum")
    if policy.require_strict_chronology and any(
        batch[index].timestamp_ms <= batch[index - 1].timestamp_ms
        for index in range(1, len(batch))
    ):
        raise ValueError("Observation ingestion batch must be strictly chronological")
    current_ms = int(time.time() * 1000) if now_ms is None else now_ms
    for observation in batch:
        if observation.available_at_ms < observation.timestamp_ms:
            raise ValueError("Observation availability cannot precede market timestamp")
        if observation.available_at_ms > current_ms + policy.max_clock_skew_ms:
            raise ValueError("Observation is not available at the ingestion clock")
        if (
            observation.close <= 0
            or observation.volume < 0
            or observation.realized_volatility < 0
            or observation.liquidity < 0
        ):
            raise ValueError("Observation contains an invalid market value")
    return batch


class SqliteObservationStore:
    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path, check_same_thread=False)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA synchronous=FULL")
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS observations (timestamp_ms INTEGER PRIMARY KEY, available_at_ms INTEGER NOT NULL, close REAL NOT NULL, volume REAL NOT NULL, realized_volatility REAL NOT NULL, liquidity REAL NOT NULL)"
        )
        self.connection.commit()
        self.lock = threading.Lock()

    def append(self, observations: Iterable[Observation]) -> int:
        batch = tuple(observations)
        inserted = 0
        with self.lock:
            for observation in batch:
                existing = self.connection.execute(
                    "SELECT available_at_ms, close, volume, realized_volatility, liquidity FROM observations WHERE timestamp_ms = ?",
                    (observation.timestamp_ms,),
                ).fetchone()
                values = (
                    observation.available_at_ms,
                    observation.close,
                    observation.volume,
                    observation.realized_volatility,
                    observation.liquidity,
                )
                if existing is not None:
                    if tuple(existing) != values:
                        raise ValueError(
                            f"Immutable observation conflict at timestamp {observation.timestamp_ms}"
                        )
                    continue
                self.connection.execute(
                    "INSERT INTO observations VALUES (?, ?, ?, ?, ?, ?)",
                    (observation.timestamp_ms, *values),
                )
                inserted += 1
            self.connection.commit()
        return inserted

    def read(self, limit: int | None = None) -> tuple[Observation, ...]:
        query = "SELECT timestamp_ms, available_at_ms, close, volume, realized_volatility, liquidity FROM observations ORDER BY timestamp_ms"
        params: tuple[Any, ...] = ()
        if limit is not None:
            if limit < 1:
                raise ValueError("Read limit must be positive")
            query += " LIMIT ?"
            params = (limit,)
        with self.lock:
            rows = self.connection.execute(query, params).fetchall()
        return tuple(Observation(*row) for row in rows)

    def close(self) -> None:
        with self.lock:
            self.connection.close()


class ProductionRuntime:
    def __init__(
        self,
        source: ObservationSource,
        store: SqliteObservationStore,
        retry: RetryPolicy | None = None,
        ingestion: IngestionPolicy | None = None,
        alert_sink: AlertSink | None = None,
    ):
        self.source = source
        self.store = store
        self.retry = retry or RetryPolicy()
        self.ingestion = ingestion or IngestionPolicy()
        self.alert_sink = alert_sink
        self.metrics = RuntimeMetrics()
        self.health = ServiceHealth("ingestion", "starting")
        self.retry.validate()
        self.ingestion.validate()

    def _fetch_with_retry(self) -> tuple[Observation, ...]:
        failure: Exception | None = None
        for attempt in range(self.retry.attempts):
            try:
                return tuple(self.source.fetch())
            except Exception as exc:
                failure = exc
                self.metrics.increment("ingestion_retries")
                if attempt + 1 < self.retry.attempts:
                    time.sleep(
                        min(
                            self.retry.base_delay_seconds * (2**attempt),
                            self.retry.max_delay_seconds,
                        )
                    )
        assert failure is not None
        raise failure

    def poll_once(self, now_ms: int | None = None) -> int:
        started = time.monotonic()
        try:
            batch = validate_ingestion_batch(
                self._fetch_with_retry(), self.ingestion, now_ms=now_ms
            )
            inserted = self.store.append(batch)
            timestamp = int(time.time() * 1000)
            self.metrics.increment("ingestion_batches")
            self.metrics.increment("ingestion_observations", len(batch))
            self.metrics.increment("stored_observations", inserted)
            self.metrics.set_gauge(
                "last_ingestion_duration_seconds", time.monotonic() - started
            )
            self.health = ServiceHealth(
                "ingestion", "healthy", last_success_ms=timestamp
            )
            return inserted
        except Exception as exc:
            timestamp = int(time.time() * 1000)
            consecutive = self.health.consecutive_failures + 1
            self.metrics.increment("ingestion_failures")
            self.health = ServiceHealth(
                "ingestion",
                "unhealthy",
                last_failure_ms=timestamp,
                consecutive_failures=consecutive,
                last_error=str(exc),
            )
            if self.alert_sink:
                self.alert_sink.emit(
                    "critical",
                    "ingestion_failure",
                    {"error": str(exc), "consecutive_failures": consecutive},
                )
            raise

    def run_forever(self, stop_event: threading.Event, interval_seconds: float) -> None:
        if interval_seconds <= 0:
            raise ValueError("Polling interval must be positive")
        while not stop_event.is_set():
            try:
                self.poll_once()
            except Exception:
                pass
            stop_event.wait(interval_seconds)

    def status(self) -> dict[str, Any]:
        return {"health": self.health, "metrics": self.metrics}
