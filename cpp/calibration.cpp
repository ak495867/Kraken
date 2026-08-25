#include "kraken_core/core.hpp"
#include "kraken_core/features.hpp"
#include "kraken_core/numeric.hpp"
#include "kraken_core/validation.hpp"

#include <cmath>
#include <cstddef>
#include <stdexcept>

namespace kraken {

namespace {

DistanceCalibration calibrate_distance_impl(const std::vector<Bar>& reference, const std::vector<Bar>& evaluation, std::int64_t decision_cutoff_ms, int reference_minimum_points, int evaluation_minimum_points, double calibration_decay) {
  const auto reference_report = inspect_integrity(reference, decision_cutoff_ms, reference_minimum_points);
  const auto evaluation_report = inspect_integrity(evaluation, decision_cutoff_ms, evaluation_minimum_points);
  detail::require_valid(reference_report);
  detail::require_valid(evaluation_report);
  if (reference.back().timestamp_ms >= evaluation.front().timestamp_ms) {
    throw std::invalid_argument("Reference observations must end before evaluation observations begin");
  }
  const auto reference_features = detail::summarize(reference);
  const auto evaluation_features = detail::summarize(evaluation);
  const double return_distance = std::abs(evaluation_features.return_mean - reference_features.return_mean) /
      std::max(reference_features.return_deviation, detail::kEpsilon);
  const double volatility_distance = std::abs(evaluation_features.volatility_mean - reference_features.volatility_mean) /
      std::max(reference_features.volatility_deviation, detail::kEpsilon);
  const double liquidity_distance = std::abs(evaluation_features.liquidity_mean - reference_features.liquidity_mean) /
      std::max(reference_features.liquidity_deviation, detail::kEpsilon);
  const double correlation_distance = std::abs(evaluation_features.correlation_value - reference_features.correlation_value);
  const double nearest_distance = std::sqrt(
      return_distance * return_distance +
      volatility_distance * volatility_distance +
      liquidity_distance * liquidity_distance +
      correlation_distance * correlation_distance);
  const auto reference_returns = detail::log_returns(reference);
  const std::size_t tail_start = reference_returns.size() / 2;
  double reference_tail_sum = 0.0;
  for (std::size_t index = tail_start; index < reference_returns.size(); ++index) {
    reference_tail_sum += reference_returns[index];
  }
  const double reference_tail_mean = reference_tail_sum / static_cast<double>(reference_returns.size() - tail_start);
  const double drift = detail::clamp(std::abs(reference_tail_mean - reference_features.return_mean) /
      std::max(reference_features.return_deviation, detail::kEpsilon), 0.0, 5.0) / 5.0;
  const double squared_distance = nearest_distance * nearest_distance;
  const double reference_fit_probability = detail::clamp(std::exp(-0.5 * squared_distance) * (1.0 + 0.5 * squared_distance), 0.0, 1.0);
  const double uncertainty = 1.0 - reference_fit_probability;
  const double confidence = detail::clamp(reference_fit_probability * (1.0 - calibration_decay * drift), 0.0, 1.0);
  return {return_distance, volatility_distance, liquidity_distance, correlation_distance, nearest_distance, uncertainty, drift, confidence};
}

}

DistanceCalibration calibrate_distance(const std::vector<Bar>& reference, const std::vector<Bar>& evaluation, std::int64_t decision_cutoff_ms) {
  return calibrate_distance_impl(reference, evaluation, decision_cutoff_ms, 6, 4, 0.25);
}

DistanceCalibration calibrate_distance_with_config(const std::vector<Bar>& reference, const std::vector<Bar>& evaluation, std::int64_t decision_cutoff_ms, const ResearchConfig& config) {
  validate_research_config(config);
  return calibrate_distance_impl(reference, evaluation, decision_cutoff_ms, config.reference_minimum_points, config.evaluation_minimum_points, config.calibration_decay);
}

}
