#pragma once

#include <cstddef>

namespace kraken {

struct NativeWorkloadMetrics {
  std::size_t input_bar_copy_count;
  std::size_t input_bar_copy_bytes;
  std::size_t temporary_double_buffer_count;
  std::size_t temporary_double_buffer_bytes;
};

NativeWorkloadMetrics estimate_sonar_workload_metrics(std::size_t observation_count, std::size_t horizon_count);
NativeWorkloadMetrics estimate_marine_dynamics_workload_metrics(std::size_t observation_count, bool derives_reference_liquidity);
NativeWorkloadMetrics estimate_calibration_workload_metrics(std::size_t reference_observation_count, std::size_t evaluation_observation_count);
NativeWorkloadMetrics estimate_regime_workload_metrics(std::size_t reference_observation_count, std::size_t evaluation_observation_count, std::size_t horizon_count);

}
