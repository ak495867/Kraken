from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from . import _core
from .audit import as_native_bars, build_integrity_audit, eligible_observations
from .config_runtime import resolve_research_config
from .models import (
    BuoyancyResilienceReport,
    CavitationRiskReport,
    DragVolatilityReport,
    MarineDynamicsReport,
    Observation,
    TidalCurrentReport,
)
from .provenance import create_run_manifest


def analyze_marine_dynamics(
    observations: Iterable[Observation],
    decision_cutoff_ms: int,
    reference_liquidity: float = 0.0,
    drag_scale: float = 1.0,
    fast_window: int = 5,
    slow_window: int = 20,
    research_config: str | None = None,
    universe_id: str | None = None,
    survivorship_controlled: bool = False,
) -> MarineDynamicsReport:
    provided = tuple(observations)
    config, canonical_config = resolve_research_config(research_config)
    if research_config is None:
        config.reference_liquidity = float(reference_liquidity)
        config.drag_scale = float(drag_scale)
        config.fast_window = int(fast_window)
        config.slow_window = int(slow_window)
        _core.validate_research_config(config)
        canonical_config = _core.serialize_research_config(config)
    minimum_points = max(8, config.slow_window + 1)
    audit = build_integrity_audit(
        provided,
        decision_cutoff_ms,
        {
            "analysis": "marine_dynamics",
            "research_config": canonical_config,
        },
        minimum_points=minimum_points,
        universe_id=universe_id,
        survivorship_controlled=survivorship_controlled,
    )
    if not audit.valid:
        details = "; ".join(item.message for item in audit.issues)
        raise ValueError(f"Integrity audit failed: {details}")
    native = _core.compute_marine_dynamics_with_config(
        as_native_bars(eligible_observations(provided, decision_cutoff_ms)),
        decision_cutoff_ms,
        config,
    )
    report = MarineDynamicsReport(
        decision_cutoff_ms=decision_cutoff_ms,
        drag=DragVolatilityReport(
            native.drag.reference_liquidity,
            native.drag.flow_intensity,
            native.drag.drag_coefficient,
            native.drag.drag_pressure,
            native.drag.adjusted_volatility,
        ),
        tidal=TidalCurrentReport(
            native.tidal.fast_window,
            native.tidal.slow_window,
            native.tidal.fast_return,
            native.tidal.slow_return,
            native.tidal.current_strength,
            native.tidal.directional_bias,
        ),
        cavitation=CavitationRiskReport(
            native.cavitation.liquidity_vacuum,
            native.cavitation.return_shock,
            native.cavitation.cavitation_score,
        ),
        buoyancy=BuoyancyResilienceReport(
            native.buoyancy.liquidity_resilience,
            native.buoyancy.volatility_load,
            native.buoyancy.buoyancy_score,
        ),
        composite_dynamics_risk=native.composite_dynamics_risk,
        integrity=audit,
    )
    return replace(
        report,
        manifest=create_run_manifest(
            {"analysis": "marine_dynamics", "research_config": canonical_config},
            {"observations": provided},
            report,
            decision_cutoff_ms,
            warnings=report.integrity.warnings,
        ),
    )
