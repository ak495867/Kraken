from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class Observation:
    timestamp_ms: int
    available_at_ms: int
    close: float
    volume: float
    realized_volatility: float
    liquidity: float


@dataclass(frozen=True)
class Echo:
    horizon: int
    displacement: float
    strength: float
    anomaly_score: float


@dataclass(frozen=True)
class ForecastBand:
    horizon: int
    lower: float
    center: float
    upper: float
    coverage: float
    sample_count: int


@dataclass(frozen=True)
class ForecastCalibrationMetric:
    horizon: int
    nominal_coverage: float
    empirical_coverage: float
    observation_count: int
    covered_observation_count: int
    mean_interval_width: float


@dataclass(frozen=True)
class ForecastCalibrationReport:
    decision_count: int
    metrics: tuple[ForecastCalibrationMetric, ...]


@dataclass(frozen=True)
class RunManifest:
    run_id: str
    engine_version: str
    decision_cutoff_ms: int | None
    configuration_sha256: str
    input_sha256: tuple[tuple[str, str], ...]
    output_sha256: str
    vendor_manifest_sha256: str | None
    platform: str
    python_version: str
    compiler: str
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class ResearchRunComparison:
    left_run_id: str
    right_run_id: str
    configuration_changed: bool
    input_changed: bool
    output_changed: bool
    environment_changed: bool
    summary: tuple[str, ...]


@dataclass(frozen=True)
class SonarReport:
    decision_cutoff_ms: int
    input_count: int
    signal_strength: float
    anomaly_score: float
    echoes: tuple[Echo, ...]
    forecast_bands: tuple[ForecastBand, ...]
    integrity: IntegrityAudit
    manifest: RunManifest | None = None


@dataclass(frozen=True)
class DistanceCalibrationReport:
    return_distance: float
    volatility_distance: float
    liquidity_distance: float
    correlation_distance: float
    nearest_regime_distance: float
    regime_risk_uncertainty: float
    calibration_drift: float
    confidence: float


@dataclass(frozen=True)
class RegimeRiskReport:
    decision_cutoff_ms: int
    regime: str
    regime_score: float
    confidence: float
    uncertainty: float
    calibration_drift: float
    sonar: SonarReport
    calibration: DistanceCalibrationReport
    integrity: IntegrityAudit
    manifest: RunManifest | None = None


@dataclass(frozen=True)
class DragVolatilityReport:
    reference_liquidity: float
    flow_intensity: float
    drag_coefficient: float
    drag_pressure: float
    adjusted_volatility: float


@dataclass(frozen=True)
class TidalCurrentReport:
    fast_window: int
    slow_window: int
    fast_return: float
    slow_return: float
    current_strength: float
    directional_bias: float


@dataclass(frozen=True)
class CavitationRiskReport:
    liquidity_vacuum: float
    return_shock: float
    cavitation_score: float


@dataclass(frozen=True)
class BuoyancyResilienceReport:
    liquidity_resilience: float
    volatility_load: float
    buoyancy_score: float


@dataclass(frozen=True)
class MarineDynamicsReport:
    decision_cutoff_ms: int
    drag: DragVolatilityReport
    tidal: TidalCurrentReport
    cavitation: CavitationRiskReport
    buoyancy: BuoyancyResilienceReport
    composite_dynamics_risk: float
    integrity: IntegrityAudit
    manifest: RunManifest | None = None


@dataclass(frozen=True)
class OptionQuote:
    timestamp_ms: int
    available_at_ms: int
    expiration_ms: int
    contract: str
    option_type: str
    strike: float
    bid: float
    ask: float
    implied_volatility: float
    open_interest: float
    volume: float
    underlying: str


@dataclass(frozen=True)
class CorporateAction:
    effective_at_ms: int
    available_at_ms: int
    underlying: str
    action_type: str
    factor: float


@dataclass(frozen=True)
class DistributionRecord:
    effective_at_ms: int
    available_at_ms: int
    underlying: str
    distribution_type: str
    amount: float


@dataclass(frozen=True)
class EarningsEvent:
    event_at_ms: int
    available_at_ms: int
    underlying: str
    fiscal_period: str
    event_type: str


@dataclass(frozen=True)
class OptionContractAdjustment:
    effective_at_ms: int
    available_at_ms: int
    underlying: str
    pre_contract: str
    post_contract: str
    strike_factor: float
    multiplier_factor: float


@dataclass(frozen=True)
class LicensedVendorManifest:
    provider: str
    dataset_id: str
    snapshot_as_of_ms: int
    price_basis: str
    equity_path: str
    options_path: str
    corporate_actions_path: str | None
    option_adjustments_path: str | None
    distributions_path: str | None
    earnings_path: str | None
    sector: str | None
    underlying_universe: str | None
    normalizer_profile: str | None
    mapping_path: str | None


@dataclass(frozen=True)
class ExchangeSession:
    session_date: str
    open_ms: int
    close_ms: int
    is_half_day: bool


@dataclass(frozen=True)
class MarketDataQualityPolicy:
    max_snapshot_lag_ms: int = 300000
    minimum_option_strikes: int = 1
    require_calls_and_puts: bool = True
    strict: bool = True


@dataclass(frozen=True)
class MarketDataQualityReport:
    valid: bool
    decision_cutoff_ms: int
    calendar_session_count: int
    checked_observation_count: int
    checked_option_quote_count: int
    duplicate_snapshot_count: int
    stale_snapshot_count: int
    incomplete_option_chain_count: int
    warnings: tuple[str, ...]
    issues: tuple[IntegrityIssue, ...]


@dataclass(frozen=True)
class LicensedDataAcceptanceReport:
    provider: str
    dataset_id: str
    accepted: bool
    verified_checks: tuple[str, ...]
    warnings: tuple[str, ...]
    authorization_sha256: str = ""
    manifest_sha256: str = ""
    input_sha256: tuple[tuple[str, str], ...] = ()
    license_name: str = ""
    authorized_by: str = ""
    authorized_at: str = ""
    expires_at: str = ""


@dataclass(frozen=True)
class CorporateActionIntegrityReport:
    valid: bool
    decision_cutoff_ms: int
    checked_action_count: int
    checked_option_count: int
    known_split_count: int
    warnings: tuple[str, ...]
    issues: tuple[IntegrityIssue, ...]


@dataclass(frozen=True)
class DistributionIntegrityReport:
    valid: bool
    decision_cutoff_ms: int
    checked_distribution_count: int
    known_distribution_count: int
    warnings: tuple[str, ...]
    issues: tuple[IntegrityIssue, ...]


@dataclass(frozen=True)
class EarningsIntegrityReport:
    valid: bool
    decision_cutoff_ms: int
    checked_event_count: int
    known_event_count: int
    warnings: tuple[str, ...]
    issues: tuple[IntegrityIssue, ...]


@dataclass(frozen=True)
class NormalizedExportReport:
    provider_profile: str
    equity_output_path: str
    options_output_path: str
    equity_row_count: int
    option_row_count: int
    configuration_fingerprint: str
    plugin_version: str | None = None
    plugin_sha256: str | None = None
    contract_path: str | None = None


@dataclass(frozen=True)
class VendorMappingPlugin:
    provider: str
    version: str
    schema: str
    mapping: dict[str, dict[str, str]]
    plugin_path: str
    contract_path: str
    sha256: str


@dataclass(frozen=True)
class ResearchBundleReport:
    output_directory: str
    files: tuple[str, ...]
    bundle_sha256: str
    report_manifest_sha256: str


@dataclass(frozen=True)
class EquityOptionsBacktestWindow:
    window_id: int
    decision_cutoff_ms: int
    evaluation_start_ms: int
    evaluation_end_ms: int
    selected_contract: str
    selected_option_type: str
    selected_strike: float
    selected_expiration_ms: int
    quote_timestamp_ms: int
    implied_move: float
    realized_log_return: float
    absolute_move_ratio: float
    implied_move_covered: bool
    regime: str
    composite_dynamics_risk: float
    drag_adjusted_volatility: float
    tidal_current_strength: float
    cavitation_score: float
    buoyancy_score: float
    integrity: IntegrityAudit


@dataclass(frozen=True)
class EquityOptionsBacktestReport:
    configuration_fingerprint: str
    train_size: int
    validation_size: int
    holding_size: int
    embargo_size: int
    sector: str | None
    underlying_universe: str | None
    windows: tuple[EquityOptionsBacktestWindow, ...]
    warnings: tuple[str, ...]
    manifest: RunManifest | None = None


@dataclass(frozen=True)
class CalibrationDiagnosticGroup:
    group_label: str
    window_count: int
    implied_move_coverage_rate: float
    mean_absolute_move_ratio: float
    mean_composite_dynamics_risk: float
    mean_drag_adjusted_volatility: float
    mean_tidal_current_strength: float
    mean_cavitation_score: float
    mean_buoyancy_score: float


@dataclass(frozen=True)
class CalibrationDiagnosticsReport:
    group_by: str
    groups: tuple[CalibrationDiagnosticGroup, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class CalibrationTimeSlice:
    slice_id: int
    start_cutoff_ms: int
    end_cutoff_ms: int
    window_count: int
    implied_move_coverage_rate: float
    mean_absolute_move_ratio: float
    mean_composite_dynamics_risk: float
    mean_drag_adjusted_volatility: float
    mean_tidal_current_strength: float
    mean_cavitation_score: float
    mean_buoyancy_score: float
    composite_risk_change_from_prior_slice: float | None


@dataclass(frozen=True)
class TimeSlicedCalibrationDiagnosticsReport:
    slice_size: int
    slices: tuple[CalibrationTimeSlice, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class TimeSliceVisualizationReport:
    output_path: str
    slice_count: int
    configuration_fingerprint: str


@dataclass(frozen=True)
class IntegrityIssue:
    code: str
    severity: str
    message: str


@dataclass(frozen=True)
class IntegrityAudit:
    valid: bool
    decision_cutoff_ms: int
    provided_input_count: int
    eligible_input_count: int
    excluded_future_timestamp_count: int
    excluded_unavailable_count: int
    feature_window_start_ms: int | None
    feature_window_end_ms: int | None
    rebalance_timing: str
    universe_id: str | None
    survivorship_controlled: bool
    chronology_check: str
    leakage_flags: tuple[str, ...]
    warnings: tuple[str, ...]
    issues: tuple[IntegrityIssue, ...]
    configuration_fingerprint: str


@dataclass(frozen=True)
class WalkForwardWindow:
    window_id: int
    train_start_ms: int
    train_end_ms: int
    validation_start_ms: int
    validation_end_ms: int
    decision_cutoff_ms: int
    evaluation_start_ms: int
    evaluation_end_ms: int
    regime: str
    confidence: float
    uncertainty: float
    realized_log_return: float
    integrity: IntegrityAudit


@dataclass(frozen=True)
class WalkForwardReport:
    configuration_fingerprint: str
    train_size: int
    validation_size: int
    test_size: int
    embargo_size: int
    windows: tuple[WalkForwardWindow, ...]
    warnings: tuple[str, ...]
    manifest: RunManifest | None = None


def to_primitive(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return {key: to_primitive(item) for key, item in asdict(value).items()}
    if isinstance(value, tuple):
        return [to_primitive(item) for item in value]
    if isinstance(value, list):
        return [to_primitive(item) for item in value]
    if isinstance(value, dict):
        return {str(key): to_primitive(item) for key, item in value.items()}
    return value
