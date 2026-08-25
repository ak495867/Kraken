# Kraken Production Runtime

Kraken’s production runtime is fail-closed and paper-first. It polls a provider endpoint that returns canonical observation records, validates timestamps and market values, stores immutable observations in SQLite WAL mode, exposes health and metrics endpoints, persists risk counters, emits JSONL alerts, and writes an execution audit log.

## Required configuration

| Variable | Purpose | Default |
| --- | --- | --- |
| `KRAKEN_OBSERVATION_URL` | HTTPS or HTTP JSON observation endpoint. | Required |
| `KRAKEN_OBSERVATION_TOKEN_ENV` | Name of the environment variable containing the provider token. | Unset |
| `KRAKEN_STORE_PATH` | Immutable SQLite observation database. | `data/observations.db` |
| `KRAKEN_ALERT_PATH` | Append-only local alert log. | `data/alerts.jsonl` |
| `KRAKEN_ALERT_URL` | Optional HTTPS alert endpoint. | Unset |
| `KRAKEN_ALERT_TOKEN_ENV` | Environment variable containing the alert endpoint token. | `KRAKEN_ALERT_TOKEN` |
| `KRAKEN_OPS_HOST` | Health and metrics bind address. | `127.0.0.1` |
| `KRAKEN_OPS_PORT` | Health and metrics port. | `8080` |
| `KRAKEN_POLL_INTERVAL_SECONDS` | Poll interval. | `60` |
| `KRAKEN_KILL_SWITCH_PATH` | Persistent kill-switch state. | `data/kill-switch.json` |
| `KRAKEN_RISK_POLICY_PATH` | Strict JSON risk-limit policy. | `configs/production_risk_limits.json` |
| `KRAKEN_RISK_STATE_PATH` | Persistent daily risk ledger. | `data/risk-state.json` |
| `KRAKEN_EXECUTION_AUDIT_PATH` | Append-only execution audit log. | `data/execution.jsonl` |
| `KRAKEN_PAPER_STATE_PATH` | Persistent paper-broker positions. | `data/paper-positions.json` |

The provider response must be either a JSON list or an object containing `observations`. Each record must include `timestamp`, `available_at`, `close`, `volume`, `realized_volatility`, and `liquidity`. Secrets are read from environment variables and are never written to logs. The risk policy is loaded from `KRAKEN_RISK_POLICY_PATH`; malformed, incomplete, or unsafe limits stop startup. If `KRAKEN_ALERT_URL` is configured, alert delivery requires HTTPS and a token environment variable; local JSONL retention remains enabled.

## Health endpoints

| Endpoint | Meaning |
| --- | --- |
| `/healthz` | Process is responding. |
| `/readyz` | Ingestion is healthy and the kill switch is inactive. |
| `/metrics` | Prometheus-compatible ingestion counters and gauges. |
| `/status` | Runtime, risk, and execution status for authenticated internal access. |

Do not expose `/status` or the operations port publicly without network authentication and TLS termination.

## Paper-first execution

The included runtime uses `PaperBroker` and does not submit live orders. The live broker interface intentionally raises an error until a provider-specific adapter, credential policy, independent certification, and deployment approval exist. The `ExecutionGateway` rejects orders when the kill switch, stale-quote, order-notional, position-notional, gross-notional, daily-loss, daily-order, or slippage limits fail.

Activate the persistent kill switch by calling `KillSwitch.activate(reason, actor)` from an authenticated operator control plane. Clear it only after the incident is reviewed and the operator calls `KillSwitch.clear(actor)`. The readiness endpoint remains unavailable while the switch is active.

## Container build

```bash
docker build -f deploy/Dockerfile -t kraken-quant:0.1.0 .
docker run --rm \
  -e KRAKEN_OBSERVATION_URL=https://provider.example/observations \
  -e KRAKEN_OBSERVATION_TOKEN_ENV=PROVIDER_TOKEN \
  -e PROVIDER_TOKEN="$PROVIDER_TOKEN" \
  -p 8080:8080 \
  -v "$PWD/data:/var/lib/kraken" \
  kraken-quant:0.1.0
```

Use a managed secret store instead of placing tokens in shell history. Back up the SQLite database, risk state, kill-switch state, alerts, paper-broker position state, and execution audit log according to the organization’s retention policy.

## Mandatory deployment approvals

Before any live-data or live-execution deployment, the operator must supply an actual provider agreement, verify entitlements and retention terms, run the empirical calibration workflow on authorized data, execute the full platform CI matrix, review risk limits independently, test recovery and kill-switch procedures, and obtain explicit approval from the responsible risk owner. This repository cannot create those approvals or prove them automatically.
