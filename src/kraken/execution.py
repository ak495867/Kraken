from __future__ import annotations

import json
import os
import threading
import time
import urllib.request
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

from .production import EnvironmentSecretStore
from .risk import RiskEngine


@dataclass(frozen=True)
class OrderRequest:
    symbol: str
    side: str
    quantity: float
    reference_price: float
    quote_timestamp_ms: int
    idempotency_key: str

    def validate(self) -> None:
        if not self.symbol.strip() or self.side.lower() not in {"buy", "sell"}:
            raise ValueError("Order symbol and side are invalid")
        if self.quantity <= 0 or self.reference_price <= 0 or self.quote_timestamp_ms <= 0 or not self.idempotency_key.strip():
            raise ValueError("Order values are invalid")


@dataclass(frozen=True)
class Fill:
    order_id: str
    status: str
    symbol: str
    side: str
    quantity: float
    execution_price: float
    filled_at_ms: int
    reason: str = ""


class Broker(Protocol):
    def submit(self, request: OrderRequest) -> Fill:
        ...


class PaperBroker:
    def __init__(self, slippage_bps: float = 0.0, state_path: str | Path | None = None):
        if slippage_bps < 0:
            raise ValueError("Paper slippage cannot be negative")
        self.slippage_bps = slippage_bps
        self.state_path = Path(state_path).expanduser().resolve() if state_path else None
        if self.state_path:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.positions: dict[str, float] = {}
        self.orders: dict[str, Fill] = {}
        self.lock = threading.RLock()
        self._load()

    def submit(self, request: OrderRequest) -> Fill:
        request.validate()
        direction = 1.0 if request.side.lower() == "buy" else -1.0
        execution_price = request.reference_price * (1.0 + direction * self.slippage_bps / 10000.0)
        fill = Fill(str(uuid.uuid4()), "filled", request.symbol, request.side.lower(), request.quantity, execution_price, int(time.time() * 1000))
        with self.lock:
            self.orders[request.idempotency_key] = fill
            self.positions[request.symbol] = self.positions.get(request.symbol, 0.0) + direction * request.quantity
            self._persist()
        return fill

    def _load(self) -> None:
        if not self.state_path or not self.state_path.exists():
            return
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
            self.positions = {str(symbol): float(quantity) for symbol, quantity in payload.get("positions", {}).items()}
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError("Paper-broker state is corrupt") from exc

    def _persist(self) -> None:
        if not self.state_path:
            return
        temporary = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        temporary.write_text(json.dumps({"positions": self.positions}, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(self.state_path)

    def position(self, symbol: str) -> float:
        with self.lock:
            return self.positions.get(symbol, 0.0)


class LiveBrokerNotConfigured:
    def submit(self, request: OrderRequest) -> Fill:
        raise RuntimeError("Live broker adapter is not configured; use a provider-specific implementation after independent certification")


class HttpJsonBroker:
    def __init__(self, url: str, token_env: str, timeout_seconds: float = 10.0, opener: Any | None = None):
        if not url.startswith("https://"):
            raise ValueError("Broker URL must use HTTPS")
        if timeout_seconds <= 0:
            raise ValueError("Broker timeout must be positive")
        self.url = url
        self.token_env = token_env
        self.timeout_seconds = timeout_seconds
        self.opener = opener or urllib.request.urlopen
        self.secrets = EnvironmentSecretStore()

    def submit(self, request: OrderRequest) -> Fill:
        request.validate()
        payload = json.dumps(asdict(request), sort_keys=True).encode("utf-8")
        token = self.secrets.require(self.token_env)
        http_request = urllib.request.Request(self.url, data=payload, headers={"Accept": "application/json", "Content-Type": "application/json", "Authorization": f"Bearer {token}", "Idempotency-Key": request.idempotency_key}, method="POST")
        with self.opener(http_request, timeout=self.timeout_seconds) as response:
            result = json.loads(response.read().decode("utf-8"))
        if not isinstance(result, dict) or result.get("status") not in {"accepted", "filled"}:
            raise RuntimeError("Broker response did not confirm an accepted or filled order")
        return Fill(str(result["order_id"]), str(result["status"]), request.symbol, request.side.lower(), float(result.get("quantity", request.quantity)), float(result["execution_price"]), int(result.get("filled_at_ms", time.time() * 1000)))


class JsonlExecutionAudit:
    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()

    def append(self, event: dict[str, Any]) -> None:
        with self.lock:
            with self.path.open("a", encoding="utf-8") as target:
                target.write(json.dumps(event, sort_keys=True) + "\n")

    def completed(self) -> dict[str, Fill]:
        completed: dict[str, Fill] = {}
        if not self.path.exists():
            return completed
        try:
            with self.lock:
                records = [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]
            for record in records:
                if record.get("event") != "order_filled":
                    continue
                request = record["request"]
                fill = record["fill"]
                completed[str(request["idempotency_key"])] = Fill(str(fill["order_id"]), str(fill["status"]), str(fill["symbol"]), str(fill["side"]), float(fill["quantity"]), float(fill["execution_price"]), int(fill["filled_at_ms"]), str(fill.get("reason", "")))
            return completed
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError("Execution audit log is corrupt") from exc


class ExecutionGateway:
    def __init__(self, broker: Broker, risk: RiskEngine, audit: JsonlExecutionAudit, mode: str = "paper", allow_live: bool = False):
        if mode not in {"paper", "live"}:
            raise ValueError("Execution mode must be paper or live")
        if mode == "live" and (not allow_live or os.environ.get("KRAKEN_LIVE_TRADING_CONFIRMATION") != "I_UNDERSTAND_LIVE_TRADING_RISK"):
            raise RuntimeError("Live execution requires explicit configuration and confirmation")
        self.broker = broker
        self.risk = risk
        self.audit = audit
        self.mode = mode
        self.allow_live = allow_live
        self.completed: dict[str, Fill] = audit.completed()
        self.lock = threading.Lock()

    def submit(self, request: OrderRequest, position_notional: float, gross_notional: float, now_ms: int | None = None) -> Fill:
        request.validate()
        with self.lock:
            existing = self.completed.get(request.idempotency_key)
        if existing is not None:
            return existing
        decision = self.risk.evaluate_order(request.symbol, request.side, request.quantity, request.reference_price, position_notional, gross_notional, request.quote_timestamp_ms, now_ms=now_ms)
        if not decision.approved:
            self.audit.append({"event": "order_rejected", "mode": self.mode, "request": asdict(request), "risk": asdict(decision)})
            raise PermissionError("Order rejected by risk controls: " + ",".join(decision.reasons))
        fill = self.broker.submit(request)
        slippage_bps = abs(fill.execution_price / request.reference_price - 1.0) * 10000.0
        if slippage_bps > self.risk.limits.max_slippage_bps:
            self.audit.append({"event": "fill_rejected", "mode": self.mode, "request": asdict(request), "fill": asdict(fill), "slippage_bps": slippage_bps})
            raise PermissionError("Execution exceeded slippage limit")
        with self.lock:
            self.completed[request.idempotency_key] = fill
        self.risk.record_order(fill.filled_at_ms)
        self.audit.append({"event": "order_filled", "mode": self.mode, "request": asdict(request), "fill": asdict(fill), "risk": asdict(decision), "slippage_bps": slippage_bps})
        return fill

    def status(self) -> dict[str, Any]:
        with self.lock:
            return {"mode": self.mode, "completed_orders": len(self.completed), "live_enabled": self.mode == "live" and self.allow_live}
