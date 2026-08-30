from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .execution import ExecutionGateway
from .production import ProductionRuntime
from .risk import RiskEngine


class OperationsHandler(BaseHTTPRequestHandler):
    runtime: ProductionRuntime
    risk: RiskEngine
    execution: ExecutionGateway

    def do_GET(self) -> None:
        if self.path == "/healthz":
            self._write(200, {"status": "ok"})
            return
        if self.path == "/readyz":
            ready = (
                self.runtime.health.status == "healthy"
                and not self.risk.kill_switch.state().active
            )
            self._write(
                200 if ready else 503,
                {
                    "ready": ready,
                    "health": self.runtime.health.status,
                    "kill_switch": self.risk.kill_switch.state().active,
                },
            )
            return
        if self.path == "/metrics":
            body = self.runtime.metrics.prometheus()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4")
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))
            return
        if self.path == "/status":
            self._write(
                200,
                {
                    "runtime": self.runtime.status(),
                    "risk": self.risk.status(),
                    "execution": self.execution.status(),
                },
            )
            return
        self._write(404, {"error": "not_found"})

    def _write(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(
            payload, default=lambda value: value.__dict__, sort_keys=True
        ).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        return


def create_operations_server(
    runtime: ProductionRuntime,
    risk: RiskEngine,
    execution: ExecutionGateway,
    host: str = "127.0.0.1",
    port: int = 8080,
) -> ThreadingHTTPServer:
    if not host.strip() or port < 0 or port > 65535:
        raise ValueError("Operations server address is invalid")
    handler = type("KrakenOperationsHandler", (OperationsHandler,), {})
    handler.runtime = runtime
    handler.risk = risk
    handler.execution = execution
    return ThreadingHTTPServer((host, port), handler)
