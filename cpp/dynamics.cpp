#include "kraken_core/core.hpp"
#include "kraken_core/features.hpp"
#include "kraken_core/numeric.hpp"
#include "kraken_core/validation.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace kraken {

DragVolatilityAdjustment compute_drag_volatility_adjustment(const std::vector<Bar>& bars, std::int64_t decision_cutoff_ms, double reference_liquidity, double drag_scale) {
  const auto report = inspect_integrity(bars, decision_cutoff_ms, 6);
  detail::require_valid(report);
  if (!detail::is_finite(reference_liquidity) || !detail::is_finite(drag_scale) || reference_liquidity < 0.0 || drag_scale < 0.0) {
    throw std::invalid_argument("Reference liquidity and drag scale must be finite non-negative values");
  }
  const auto& active = bars;
  std::vector<double> log_volumes;
  log_volumes.reserve(active.size());
  for (const auto& bar : active) {
    log_volumes.push_back(std::log1p(bar.volume));
  }
  const double baseline_log_liquidity = reference_liquidity > 0.0 ? std::log1p(reference_liquidity) : detail::mean(detail::log_liquidity_values(active));
  const double reported_reference_liquidity = reference_liquidity > 0.0 ? reference_liquidity : std::expm1(baseline_log_liquidity);
  const double flow_intensity = std::abs(log_volumes.back() - detail::mean(log_volumes));
  const double drag_coefficient = 0.47 + 0.18 * detail::clamp(flow_intensity / 3.0, 0.0, 1.0);
  const double liquidity_density = std::sqrt(std::max(std::log1p(active.back().liquidity) / std::max(baseline_log_liquidity, detail::kEpsilon), detail::kEpsilon));
  const double drag_pressure = 0.5 * liquidity_density * drag_coefficient * active.back().realized_volatility * active.back().realized_volatility;
  const double adjusted_volatility = active.back().realized_volatility * std::sqrt(1.0 + drag_scale * drag_pressure);
  return {reported_reference_liquidity, flow_intensity, drag_coefficient, drag_pressure, adjusted_volatility};
}

TidalCurrentResult compute_tidal_current(const std::vector<Bar>& bars, std::int64_t decision_cutoff_ms, int fast_window, int slow_window) {
  const auto report = inspect_integrity(bars, decision_cutoff_ms, 4);
  detail::require_valid(report);
  if (fast_window <= 0 || slow_window <= fast_window) {
    throw std::invalid_argument("Tidal windows must be positive and slow_window must exceed fast_window");
  }
  const auto& active = bars;
  if (active.size() <= static_cast<std::size_t>(slow_window)) {
    throw std::invalid_argument("Insufficient history for the requested tidal windows");
  }
  const double fast_return = std::log(active.back().close / active[active.size() - static_cast<std::size_t>(fast_window) - 1].close);
  const double slow_return = std::log(active.back().close / active[active.size() - static_cast<std::size_t>(slow_window) - 1].close);
  const auto returns = detail::log_returns(active);
  const double expected_fast = slow_return * static_cast<double>(fast_window) / static_cast<double>(slow_window);
  const double current_strength = std::abs(fast_return - expected_fast) / std::max(detail::standard_deviation(returns) * std::sqrt(static_cast<double>(fast_window)), detail::kEpsilon);
  const double directional_bias = detail::clamp(fast_return / std::max(std::abs(slow_return), detail::kEpsilon), -3.0, 3.0);
  return {fast_window, slow_window, fast_return, slow_return, current_strength, directional_bias};
}

CavitationRiskResult compute_cavitation_risk(const std::vector<Bar>& bars, std::int64_t decision_cutoff_ms) {
  const auto report = inspect_integrity(bars, decision_cutoff_ms, 8);
  detail::require_valid(report);
  const auto& active = bars;
  const auto returns = detail::log_returns(active);
  const std::size_t recent_count = std::min<std::size_t>(5, active.size() - 1);
  std::vector<double> baseline_liquidity;
  std::vector<double> recent_liquidity;
  baseline_liquidity.reserve(active.size() - recent_count);
  recent_liquidity.reserve(recent_count);
  for (std::size_t index = 0; index < active.size() - recent_count; ++index) {
    baseline_liquidity.push_back(std::log1p(active[index].liquidity));
  }
  for (std::size_t index = active.size() - recent_count; index < active.size(); ++index) {
    recent_liquidity.push_back(std::log1p(active[index].liquidity));
  }
  const double liquidity_vacuum = detail::clamp((detail::mean(baseline_liquidity) - detail::mean(recent_liquidity)) / std::max(std::abs(detail::mean(baseline_liquidity)), detail::kEpsilon), 0.0, 1.0);
  const double return_shock = std::abs((returns.back() - detail::mean(returns)) / std::max(detail::standard_deviation(returns), detail::kEpsilon));
  const double cavitation_score = detail::clamp(0.60 * liquidity_vacuum + 0.40 * detail::clamp(return_shock / 4.0, 0.0, 1.0), 0.0, 1.0);
  return {liquidity_vacuum, return_shock, cavitation_score};
}

BuoyancyResilienceResult compute_buoyancy_resilience(const std::vector<Bar>& bars, std::int64_t decision_cutoff_ms) {
  const auto report = inspect_integrity(bars, decision_cutoff_ms, 6);
  detail::require_valid(report);
  const auto& active = bars;
  const auto liquidity = detail::log_liquidity_values(active);
  const auto volatility = detail::volatility_values(active);
  const double liquidity_resilience = std::log1p(active.back().liquidity) / std::max(detail::mean(liquidity), detail::kEpsilon);
  const double volatility_load = active.back().realized_volatility / std::max(detail::mean(volatility), detail::kEpsilon);
  const double buoyancy_score = detail::clamp(liquidity_resilience / std::max(volatility_load, detail::kEpsilon), 0.0, 2.0) / 2.0;
  return {liquidity_resilience, volatility_load, buoyancy_score};
}

MarineDynamicsResult compute_marine_dynamics(const std::vector<Bar>& bars, std::int64_t decision_cutoff_ms, double reference_liquidity, double drag_scale, int fast_window, int slow_window) {
  const auto drag = compute_drag_volatility_adjustment(bars, decision_cutoff_ms, reference_liquidity, drag_scale);
  const auto tidal = compute_tidal_current(bars, decision_cutoff_ms, fast_window, slow_window);
  const auto cavitation = compute_cavitation_risk(bars, decision_cutoff_ms);
  const auto buoyancy = compute_buoyancy_resilience(bars, decision_cutoff_ms);
  const auto& active = bars;
  const double baseline_volatility = std::max(active.back().realized_volatility, detail::kEpsilon);
  const double drag_increment = detail::clamp(drag.adjusted_volatility / baseline_volatility - 1.0, 0.0, 1.0);
  const double tidal_component = detail::clamp(tidal.current_strength / 3.0, 0.0, 1.0);
  const double composite_dynamics_risk = detail::clamp(
      0.25 * drag_increment +
      0.25 * tidal_component +
      0.35 * cavitation.cavitation_score +
      0.15 * (1.0 - buoyancy.buoyancy_score),
      0.0,
      1.0);
  return {drag, tidal, cavitation, buoyancy, composite_dynamics_risk};
}

MarineDynamicsResult compute_marine_dynamics_with_config(const std::vector<Bar>& bars, std::int64_t decision_cutoff_ms, const ResearchConfig& config) {
  validate_research_config(config);
  return compute_marine_dynamics(bars, decision_cutoff_ms, config.reference_liquidity, config.drag_scale, config.fast_window, config.slow_window);
}

}
