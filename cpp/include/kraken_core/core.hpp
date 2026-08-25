#pragma once

#include "kraken_core/config.hpp"
#include "kraken_core/types.hpp"

#include <cstdint>
#include <vector>

namespace kraken {

IntegrityReport inspect_integrity(const std::vector<Bar>& bars, std::int64_t decision_cutoff_ms, int minimum_points);
SonarResult compute_sonar(const std::vector<Bar>& bars, const std::vector<int>& horizons, std::int64_t decision_cutoff_ms);
SonarResult compute_sonar_with_config(const std::vector<Bar>& bars, std::int64_t decision_cutoff_ms, const ResearchConfig& config);
DistanceCalibration calibrate_distance(const std::vector<Bar>& reference, const std::vector<Bar>& evaluation, std::int64_t decision_cutoff_ms);
DistanceCalibration calibrate_distance_with_config(const std::vector<Bar>& reference, const std::vector<Bar>& evaluation, std::int64_t decision_cutoff_ms, const ResearchConfig& config);
RegimeResult classify_regime(const std::vector<Bar>& reference, const std::vector<Bar>& evaluation, const std::vector<int>& horizons, std::int64_t decision_cutoff_ms);
RegimeResult classify_regime_with_config(const std::vector<Bar>& reference, const std::vector<Bar>& evaluation, std::int64_t decision_cutoff_ms, const ResearchConfig& config);
DragVolatilityAdjustment compute_drag_volatility_adjustment(const std::vector<Bar>& bars, std::int64_t decision_cutoff_ms, double reference_liquidity, double drag_scale);
TidalCurrentResult compute_tidal_current(const std::vector<Bar>& bars, std::int64_t decision_cutoff_ms, int fast_window, int slow_window);
CavitationRiskResult compute_cavitation_risk(const std::vector<Bar>& bars, std::int64_t decision_cutoff_ms);
BuoyancyResilienceResult compute_buoyancy_resilience(const std::vector<Bar>& bars, std::int64_t decision_cutoff_ms);
MarineDynamicsResult compute_marine_dynamics(const std::vector<Bar>& bars, std::int64_t decision_cutoff_ms, double reference_liquidity, double drag_scale, int fast_window, int slow_window);
MarineDynamicsResult compute_marine_dynamics_with_config(const std::vector<Bar>& bars, std::int64_t decision_cutoff_ms, const ResearchConfig& config);

}
