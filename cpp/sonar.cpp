#include "kraken_core/core.hpp"
#include "kraken_core/features.hpp"
#include "kraken_core/numeric.hpp"
#include "kraken_core/validation.hpp"

#include <cmath>
#include <stdexcept>

namespace kraken {

namespace {

SonarResult compute_sonar_impl(const std::vector<Bar>& bars, const std::vector<int>& horizons, std::int64_t decision_cutoff_ms, int minimum_points, double forecast_coverage) {
  const auto report = inspect_integrity(bars, decision_cutoff_ms, minimum_points);
  detail::require_valid(report);
  if (horizons.empty()) {
    throw std::invalid_argument("At least one positive forecast horizon is required");
  }
  const auto& active = bars;
  const auto returns = detail::log_returns(active);
  const double return_mean = detail::mean(returns);
  const double return_deviation = detail::standard_deviation(returns);
  const double latest_standardized = std::abs((returns.back() - return_mean) / std::max(return_deviation, detail::kEpsilon));
  const double latest_volatility = std::max(active.back().realized_volatility, detail::kEpsilon);
  SonarResult result{0.0, latest_standardized, {}, {}, "valid"};
  double strength_sum = 0.0;
  for (const int horizon : horizons) {
    if (horizon <= 0 || static_cast<std::size_t>(horizon) >= active.size()) {
      throw std::invalid_argument("Each horizon must be positive and shorter than the eligible history");
    }
    const std::size_t start = active.size() - static_cast<std::size_t>(horizon) - 1;
    const double displacement = std::log(active.back().close / active[start].close);
    const double expected_scale = std::max(latest_volatility * std::sqrt(static_cast<double>(horizon)), detail::kEpsilon);
    const double strength = std::abs(displacement) / expected_scale;
    const double horizon_anomaly = std::abs(displacement - return_mean * static_cast<double>(horizon)) /
        std::max(return_deviation * std::sqrt(static_cast<double>(horizon)), detail::kEpsilon);
    std::vector<double> historical_horizon_returns;
    historical_horizon_returns.reserve(active.size() - static_cast<std::size_t>(horizon));
    for (std::size_t end = static_cast<std::size_t>(horizon); end < active.size(); ++end) {
      historical_horizon_returns.push_back(std::log(active[end].close / active[end - static_cast<std::size_t>(horizon)].close));
    }
    if (historical_horizon_returns.size() < 4) {
      throw std::invalid_argument("Insufficient empirical forecast samples for the requested horizon");
    }
    const double lower = detail::quantile(historical_horizon_returns, (1.0 - forecast_coverage) / 2.0);
    const double center = detail::quantile(historical_horizon_returns, 0.5);
    const double upper = detail::quantile(historical_horizon_returns, 1.0 - (1.0 - forecast_coverage) / 2.0);
    result.echoes.push_back({horizon, displacement, strength, horizon_anomaly});
    result.forecast_bands.push_back({horizon, lower, center, upper, forecast_coverage, static_cast<int>(historical_horizon_returns.size())});
    strength_sum += strength;
  }
  result.signal_strength = strength_sum / static_cast<double>(horizons.size());
  return result;
}

}

SonarResult compute_sonar(const std::vector<Bar>& bars, const std::vector<int>& horizons, std::int64_t decision_cutoff_ms) {
  return compute_sonar_impl(bars, horizons, decision_cutoff_ms, 4, 0.90);
}

SonarResult compute_sonar_with_config(const std::vector<Bar>& bars, std::int64_t decision_cutoff_ms, const ResearchConfig& config) {
  validate_research_config(config);
  return compute_sonar_impl(bars, config.sonar_horizons, decision_cutoff_ms, config.minimum_points, config.forecast_coverage);
}

}
