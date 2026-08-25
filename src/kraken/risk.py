from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RiskLimits:
    max_order_notional: float
    max_position_notional: float
    max_gross_notional: float
    max_daily_loss: float
    max_orders_per_day: int
    max_data_age_seconds: float
    max_slippage_bps: float

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "RiskLimits":
        required = {"max_order_notional", "max_position_notional", "max_gross_notional", "max_daily_loss", "max_orders_per_day", "max_data_age_seconds", "max_slippage_bps"}
        if set(payload) != required:
            raise ValueError("Risk policy keys must exactly match the declared risk-limit contract")
        limits = cls(float(payload["max_order_notional"]), float(payload["max_position_notional"]), float(payload["max_gross_notional"]), float(payload["max_daily_loss"]), int(payload["max_orders_per_day"]), float(payload["max_data_age_seconds"]), float(payload["max_slippage_bps"]))
        limits.validate()
        return limits

    def validate(self) -> None:
        values = (self.max_order_notional, self.max_position_notional, self.max_gross_notional, self.max_daily_loss, self.max_data_age_seconds, self.max_slippage_bps)
        if any(value <= 0 for value in values):
            raise ValueError("Risk limits must be positive")
        if self.max_orders_per_day < 1:
            raise ValueError("Maximum orders per day must be positive")
        if self.max_position_notional > self.max_gross_notional:
            raise ValueError("Position limit cannot exceed gross limit")


@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    reasons: tuple[str, ...]
    evaluated_at_ms: int
    order_notional: float
    projected_position_notional: float
    projected_gross_notional: float


@dataclass(frozen=True)
class KillSwitchState:
    active: bool
    reason: str
    actor: str
    changed_at_ms: int


class KillSwitch:
    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()

    def state(self) -> KillSwitchState:
        with self.lock:
            if not self.path.exists():
                return KillSwitchState(False, "", "", 0)
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        return KillSwitchState(bool(payload.get("active")), str(payload.get("reason", "")), str(payload.get("actor", "")), int(payload.get("changed_at_ms", 0)))

    def activate(self, reason: str, actor: str) -> KillSwitchState:
        if not reason.strip() or not actor.strip():
            raise ValueError("Kill-switch activation requires reason and actor")
        state = KillSwitchState(True, reason.strip(), actor.strip(), int(time.time() * 1000))
        self._write(state)
        return state

    def clear(self, actor: str) -> KillSwitchState:
        if not actor.strip():
            raise ValueError("Kill-switch clearance requires actor")
        state = KillSwitchState(False, "", actor.strip(), int(time.time() * 1000))
        self._write(state)
        return state

    def _write(self, state: KillSwitchState) -> None:
        payload = {"active": state.active, "reason": state.reason, "actor": state.actor, "changed_at_ms": state.changed_at_ms}
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        with self.lock:
            temporary.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
            temporary.replace(self.path)


def load_risk_limits(path: str | Path) -> RiskLimits:
    source = Path(path).expanduser().resolve()
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Risk policy cannot be read") from exc
    if not isinstance(payload, dict):
        raise ValueError("Risk policy must be a JSON object")
    return RiskLimits.from_mapping(payload)


class RiskEngine:
    def __init__(self, limits: RiskLimits, kill_switch: KillSwitch, state_path: str | Path | None = None):
        limits.validate()
        self.limits = limits
        self.kill_switch = kill_switch
        self.state_path = Path(state_path).expanduser().resolve() if state_path else None
        if self.state_path:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.orders_by_day: dict[str, int] = {}
        self.daily_pnl: dict[str, float] = {}
        self.lock = threading.RLock()
        self._load()

    def record_order(self, timestamp_ms: int) -> None:
        day = time.strftime("%Y-%m-%d", time.gmtime(timestamp_ms / 1000))
        with self.lock:
            self.orders_by_day[day] = self.orders_by_day.get(day, 0) + 1
            self._persist()

    def record_pnl(self, timestamp_ms: int, pnl: float) -> None:
        day = time.strftime("%Y-%m-%d", time.gmtime(timestamp_ms / 1000))
        with self.lock:
            self.daily_pnl[day] = self.daily_pnl.get(day, 0.0) + pnl
            self._persist()

    def _load(self) -> None:
        if not self.state_path or not self.state_path.exists():
            return
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
            self.orders_by_day = {str(key): int(value) for key, value in payload.get("orders_by_day", {}).items()}
            self.daily_pnl = {str(key): float(value) for key, value in payload.get("daily_pnl", {}).items()}
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError("Risk state is corrupt") from exc

    def _persist(self) -> None:
        if not self.state_path:
            return
        payload = {"orders_by_day": self.orders_by_day, "daily_pnl": self.daily_pnl}
        temporary = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(self.state_path)

    def evaluate_order(self, symbol: str, side: str, quantity: float, reference_price: float, position_notional: float, gross_notional: float, quote_timestamp_ms: int, now_ms: int | None = None) -> RiskDecision:
        evaluated_at = int(time.time() * 1000) if now_ms is None else now_ms
        order_notional = abs(quantity * reference_price)
        signed_notional = order_notional if side.lower() == "buy" else -order_notional
        projected_position = abs(position_notional + signed_notional)
        projected_gross = gross_notional + order_notional
        reasons: list[str] = []
        if self.kill_switch.state().active:
            reasons.append("kill_switch_active")
        if not symbol.strip():
            reasons.append("missing_symbol")
        if side.lower() not in {"buy", "sell"}:
            reasons.append("invalid_side")
        if quantity <= 0 or reference_price <= 0:
            reasons.append("invalid_order_values")
        if order_notional > self.limits.max_order_notional:
            reasons.append("order_notional_limit")
        if projected_position > self.limits.max_position_notional:
            reasons.append("position_notional_limit")
        if projected_gross > self.limits.max_gross_notional:
            reasons.append("gross_notional_limit")
        if evaluated_at - quote_timestamp_ms > int(self.limits.max_data_age_seconds * 1000):
            reasons.append("stale_quote")
        day = time.strftime("%Y-%m-%d", time.gmtime(evaluated_at / 1000))
        with self.lock:
            if self.orders_by_day.get(day, 0) >= self.limits.max_orders_per_day:
                reasons.append("daily_order_limit")
            if self.daily_pnl.get(day, 0.0) <= -self.limits.max_daily_loss:
                reasons.append("daily_loss_limit")
        return RiskDecision(not reasons, tuple(reasons), evaluated_at, order_notional, projected_position, projected_gross)

    def status(self, now_ms: int | None = None) -> dict[str, Any]:
        current = int(time.time() * 1000) if now_ms is None else now_ms
        day = time.strftime("%Y-%m-%d", time.gmtime(current / 1000))
        with self.lock:
            return {"kill_switch": self.kill_switch.state(), "orders_today": self.orders_by_day.get(day, 0), "daily_pnl": self.daily_pnl.get(day, 0.0), "limits": self.limits}
