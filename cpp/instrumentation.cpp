#include "kraken_core/instrumentation.hpp"

#include "kraken_core/types.hpp"

#include <stdexcept>

namespace kraken {

NativeWorkloadMetrics estimate_sonar_workload_metrics(std::size_t observation_count, std::size_t horizon_count) {
  if (observation_count < 2 || horizon_count == 0) {
    throw std::invalid_argument("Sonar workload instrumentation requires at least two observations and one horizon");
  }
  return {0U, 0U, 1U, (observation_count - 1U) * sizeof(double)};
}

NativeWorkloadMetrics estimate_marine_dynamics_workload_metrics(std::size_t observation_count, bool derives_reference_liquidity) {
  if (observation_count < 8) {
    throw std::invalid_argument("Marine-dynamics workload instrumentation requires at least eight observations");
  }
  const std::size_t derived_liquidity_buffers = derives_reference_liquidity ? 1U : 0U;
  const std::size_t temporary_double_buffer_count = 7U + derived_liquidity_buffers;
  const std::size_t temporary_double_elements = 6U * observation_count - 2U + (derives_reference_liquidity ? observation_count : 0U);
  return {0U, 0U, temporary_double_buffer_count, temporary_double_elements * sizeof(double)};
}

NativeWorkloadMetrics estimate_calibration_workload_metrics(std::size_t reference_observation_count, std::size_t evaluation_observation_count) {
  if (reference_observation_count < 2 || evaluation_observation_count < 2) {
    throw std::invalid_argument("Calibration workload instrumentation requires at least two reference and evaluation observations");
  }
  const std::size_t temporary_double_elements = 5U * reference_observation_count + 4U * evaluation_observation_count - 5U;
  return {0U, 0U, 9U, temporary_double_elements * sizeof(double)};
}

NativeWorkloadMetrics estimate_regime_workload_metrics(std::size_t reference_observation_count, std::size_t evaluation_observation_count, std::size_t horizon_count) {
  if (horizon_count == 0U) {
    throw std::invalid_argument("Regime workload instrumentation requires at least one horizon");
  }
  const auto calibration = estimate_calibration_workload_metrics(reference_observation_count, evaluation_observation_count);
  const auto sonar = estimate_sonar_workload_metrics(evaluation_observation_count, horizon_count);
  return {0U, 0U, calibration.temporary_double_buffer_count + sonar.temporary_double_buffer_count, calibration.temporary_double_buffer_bytes + sonar.temporary_double_buffer_bytes};
}

}
