import os
import signal
import threading

from kraken.execution import ExecutionGateway, JsonlExecutionAudit, PaperBroker
from kraken.operations import create_operations_server
from kraken.production import CompositeAlertSink, HttpJsonAlertSink, HttpJsonObservationSource, IngestionPolicy, JsonlAlertSink, ProductionRuntime, RetryPolicy, SqliteObservationStore
from kraken.risk import KillSwitch, RiskEngine, load_risk_limits


def number(name: str, default: float) -> float:
    return float(os.environ.get(name, str(default)))


def integer(name: str, default: int) -> int:
    return int(os.environ.get(name, str(default)))


def main() -> None:
    url = os.environ.get("KRAKEN_OBSERVATION_URL")
    if not url:
        raise SystemExit("KRAKEN_OBSERVATION_URL is required")
    source = HttpJsonObservationSource(url, token_env=os.environ.get("KRAKEN_OBSERVATION_TOKEN_ENV"))
    store = SqliteObservationStore(os.environ.get("KRAKEN_STORE_PATH", "data/observations.db"))
    alert_sinks = [JsonlAlertSink(os.environ.get("KRAKEN_ALERT_PATH", "data/alerts.jsonl"))]
    alert_url = os.environ.get("KRAKEN_ALERT_URL")
    if alert_url:
        alert_sinks.append(HttpJsonAlertSink(alert_url, os.environ.get("KRAKEN_ALERT_TOKEN_ENV", "KRAKEN_ALERT_TOKEN")))
    runtime = ProductionRuntime(
        source,
        store,
        retry=RetryPolicy(integer("KRAKEN_RETRY_ATTEMPTS", 3), number("KRAKEN_RETRY_BASE_SECONDS", 0.5), number("KRAKEN_RETRY_MAX_SECONDS", 30.0)),
        ingestion=IngestionPolicy(integer("KRAKEN_MAX_CLOCK_SKEW_MS", 300000), integer("KRAKEN_MAX_BATCH_SIZE", 100000)),
        alert_sink=CompositeAlertSink(*alert_sinks),
    )
    kill_switch = KillSwitch(os.environ.get("KRAKEN_KILL_SWITCH_PATH", "data/kill-switch.json"))
    risk = RiskEngine(
        load_risk_limits(os.environ.get("KRAKEN_RISK_POLICY_PATH", "configs/production_risk_limits.json")),
        kill_switch,
        state_path=os.environ.get("KRAKEN_RISK_STATE_PATH", "data/risk-state.json"),
    )
    execution = ExecutionGateway(PaperBroker(number("KRAKEN_PAPER_SLIPPAGE_BPS", 0), os.environ.get("KRAKEN_PAPER_STATE_PATH", "data/paper-positions.json")), risk, JsonlExecutionAudit(os.environ.get("KRAKEN_EXECUTION_AUDIT_PATH", "data/execution.jsonl")))
    server = create_operations_server(runtime, risk, execution, os.environ.get("KRAKEN_OPS_HOST", "127.0.0.1"), integer("KRAKEN_OPS_PORT", 8080))
    stop_event = threading.Event()

    def stop(*_args):
        stop_event.set()
        server.shutdown()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    try:
        runtime.run_forever(stop_event, number("KRAKEN_POLL_INTERVAL_SECONDS", 60))
    finally:
        server.server_close()
        store.close()


if __name__ == "__main__":
    main()
