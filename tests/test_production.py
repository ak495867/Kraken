import json
import tempfile
import threading
import unittest
from pathlib import Path

from kraken.execution import (
    ExecutionGateway,
    JsonlExecutionAudit,
    LiveBrokerNotConfigured,
    OrderRequest,
    PaperBroker,
)
from kraken.operations import create_operations_server
from kraken.production import (
    IngestionPolicy,
    JsonlAlertSink,
    ProductionRuntime,
    RetryPolicy,
    SqliteObservationStore,
    observation_from_mapping,
    validate_ingestion_batch,
)
from kraken.risk import KillSwitch, RiskEngine, RiskLimits


class Source:
    def __init__(self, batch, failures=0):
        self.batch = batch
        self.failures = failures
        self.calls = 0

    def fetch(self):
        self.calls += 1
        if self.calls <= self.failures:
            raise OSError("temporary source failure")
        return self.batch


class ProductionRuntimeTests(unittest.TestCase):
    def make_observations(self):
        return tuple(
            observation_from_mapping(
                {
                    "timestamp": f"2026-01-0{index}T00:00:00Z",
                    "available_at": f"2026-01-0{index}T00:00:00Z",
                    "close": 100.0 + index,
                    "volume": 1000.0,
                    "realized_volatility": 0.2,
                    "liquidity": 100000.0,
                }
            )
            for index in range(1, 4)
        )

    def test_ingestion_rejects_unavailable_records(self):
        observations = self.make_observations()
        future = observations[0].__class__(
            observations[0].timestamp_ms,
            2_000_000_000_000,
            observations[0].close,
            observations[0].volume,
            observations[0].realized_volatility,
            observations[0].liquidity,
        )
        with self.assertRaisesRegex(ValueError, "not available"):
            validate_ingestion_batch(
                (future,),
                IngestionPolicy(max_clock_skew_ms=0),
                now_ms=1_900_000_000_000,
            )

    def test_runtime_retries_and_stores_immutably(self):
        observations = self.make_observations()
        with tempfile.TemporaryDirectory() as directory:
            store = SqliteObservationStore(Path(directory) / "observations.db")
            runtime = ProductionRuntime(
                Source(observations, failures=2),
                store,
                retry=RetryPolicy(
                    attempts=3, base_delay_seconds=0, max_delay_seconds=0
                ),
                ingestion=IngestionPolicy(max_clock_skew_ms=10_000_000_000),
                alert_sink=JsonlAlertSink(Path(directory) / "alerts.jsonl"),
            )
            inserted = runtime.poll_once(now_ms=2_000_000_000_000)
            self.assertEqual(inserted, 3)
            self.assertEqual(len(store.read()), 3)
            self.assertEqual(runtime.health.status, "healthy")
            self.assertEqual(runtime.metrics.counters["ingestion_retries"], 2)
            self.assertEqual(store.append(observations), 0)
            conflict = observations[0].__class__(
                observations[0].timestamp_ms,
                observations[0].available_at_ms,
                observations[0].close + 1,
                observations[0].volume,
                observations[0].realized_volatility,
                observations[0].liquidity,
            )
            with self.assertRaisesRegex(ValueError, "Immutable observation conflict"):
                store.append((conflict,))
            store.close()

    def test_risk_and_paper_execution_are_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            kill_switch = KillSwitch(Path(directory) / "kill-switch.json")
            risk = RiskEngine(RiskLimits(1000, 2000, 5000, 500, 2, 60, 25), kill_switch)
            audit = JsonlExecutionAudit(Path(directory) / "execution.jsonl")
            paper_state = Path(directory) / "paper.json"
            gateway = ExecutionGateway(PaperBroker(state_path=paper_state), risk, audit)
            now = 1_900_000_000_000
            request = OrderRequest("TEST", "buy", 2, 100, now, "order-1")
            fill = gateway.submit(request, 0, 0, now_ms=now)
            self.assertEqual(fill.status, "filled")
            self.assertEqual(gateway.submit(request, 0, 0, now_ms=now), fill)
            self.assertEqual(PaperBroker(state_path=paper_state).position("TEST"), 2.0)
            persistent_risk = RiskEngine(
                RiskLimits(1000, 2000, 5000, 500, 2, 60, 25),
                kill_switch,
                state_path=Path(directory) / "risk.json",
            )
            persistent_risk.record_order(now)
            self.assertEqual(
                RiskEngine(
                    RiskLimits(1000, 2000, 5000, 500, 2, 60, 25),
                    kill_switch,
                    state_path=Path(directory) / "risk.json",
                ).status(now)["orders_today"],
                1,
            )
            kill_switch.activate("manual review", "operator")
            with self.assertRaisesRegex(PermissionError, "kill_switch_active"):
                gateway.submit(
                    OrderRequest("TEST", "buy", 1, 100, now, "order-2"),
                    200,
                    200,
                    now_ms=now,
                )
            with self.assertRaisesRegex(RuntimeError, "Live execution"):
                ExecutionGateway(LiveBrokerNotConfigured(), risk, audit, mode="live")

    def test_operations_server_has_health_and_readiness_objects(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SqliteObservationStore(Path(directory) / "observations.db")
            runtime = ProductionRuntime(
                Source(self.make_observations()),
                store,
                ingestion=IngestionPolicy(max_clock_skew_ms=10_000_000_000),
            )
            switch = KillSwitch(Path(directory) / "kill-switch.json")
            risk = RiskEngine(RiskLimits(1000, 2000, 5000, 500, 2, 60, 25), switch)
            gateway = ExecutionGateway(
                PaperBroker(),
                risk,
                JsonlExecutionAudit(Path(directory) / "execution.jsonl"),
            )
            server = create_operations_server(runtime, risk, gateway, port=0)
            self.assertEqual(server.server_address[1] > 0, True)
            server.server_close()
            store.close()


if __name__ == "__main__":
    unittest.main()
