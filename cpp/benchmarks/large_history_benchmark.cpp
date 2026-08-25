#include "kraken_core/core.hpp"

#include "kraken_core/instrumentation.hpp"

#include <chrono>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <string>
#include <vector>

namespace {

std::vector<kraken::Bar> make_bars(std::size_t count) {
  std::vector<kraken::Bar> bars;
  bars.reserve(count);
  for (std::size_t index = 0; index < count; ++index) {
    const double value = static_cast<double>(index);
    bars.push_back({
        1'600'000'000'000LL + static_cast<std::int64_t>(index) * 60'000LL,
        1'600'000'000'000LL + static_cast<std::int64_t>(index) * 60'000LL,
        100.0 + 0.0008 * value + 2.0 * std::sin(value / 97.0),
        1'000'000.0 + 20'000.0 * std::abs(std::sin(value / 41.0)),
        0.012 + 0.004 * std::abs(std::sin(value / 131.0)),
        2'500'000.0 + 100'000.0 * std::abs(std::cos(value / 73.0)),
    });
  }
  return bars;
}

double percentile(std::vector<double> values, double proportion) {
  std::sort(values.begin(), values.end());
  const std::size_t index = std::min(values.size() - 1U, static_cast<std::size_t>(std::ceil(proportion * static_cast<double>(values.size()))) - 1U);
  return values[index];
}

template <typename Callable>
void run_benchmark(const std::string& name, std::size_t observations, int iterations, int samples, const std::string& compiler, const kraken::NativeWorkloadMetrics& metrics, Callable callable) {
  volatile double checksum = 0.0;
  std::vector<double> elapsed_samples;
  elapsed_samples.reserve(static_cast<std::size_t>(samples));
  for (int sample = 0; sample < samples; ++sample) {
    const auto started = std::chrono::steady_clock::now();
    for (int iteration = 0; iteration < iterations; ++iteration) {
      checksum += callable();
    }
    elapsed_samples.push_back(std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - started).count());
  }
  std::cout << name << ',' << observations << ',' << iterations << ',' << samples << ',' << std::fixed << std::setprecision(3) << percentile(elapsed_samples, 0.50) << ',' << percentile(elapsed_samples, 0.95) << ',' << checksum << ',' << compiler << ',' << metrics.input_bar_copy_count << ',' << metrics.input_bar_copy_bytes << ',' << metrics.temporary_double_buffer_count << ',' << metrics.temporary_double_buffer_bytes << '\n';
}

std::string compiler_identity() {
#if defined(__clang__)
  return "clang-" + std::to_string(__clang_major__) + "." + std::to_string(__clang_minor__) + "." + std::to_string(__clang_patchlevel__);
#elif defined(__GNUC__)
  return "gcc-" + std::to_string(__GNUC__) + "." + std::to_string(__GNUC_MINOR__) + "." + std::to_string(__GNUC_PATCHLEVEL__);
#elif defined(_MSC_VER)
  return "msvc-" + std::to_string(_MSC_VER);
#else
  return "unknown";
#endif
}

}

int main(int argc, char** argv) {
  const std::size_t observations = argc > 1 ? static_cast<std::size_t>(std::strtoull(argv[1], nullptr, 10)) : 200'000U;
  const int iterations = argc > 2 ? std::atoi(argv[2]) : 5;
  const int samples = argc > 3 ? std::atoi(argv[3]) : 9;
  if (observations < 32 || iterations <= 0 || samples < 3) {
    std::cerr << "observations must be at least 32, iterations must be positive, and samples must be at least three\n";
    return 2;
  }
  const auto bars = make_bars(observations);
  const std::size_t reference_count = observations * 3U / 5U;
  const std::vector<kraken::Bar> reference(bars.begin(), bars.begin() + static_cast<std::ptrdiff_t>(reference_count));
  const std::vector<kraken::Bar> evaluation(bars.begin() + static_cast<std::ptrdiff_t>(reference_count), bars.end());
  const std::int64_t cutoff = bars.back().timestamp_ms;
  const std::string compiler = compiler_identity();
  std::cout << "benchmark,observations,iterations,samples,p50_ms,p95_ms,checksum,compiler,input_bar_copy_count,input_bar_copy_bytes,temporary_double_buffer_count,temporary_double_buffer_bytes\n";
  run_benchmark("sonar_large_history", observations, iterations, samples, compiler, kraken::estimate_sonar_workload_metrics(observations, 4U), [&] {
    return kraken::compute_sonar(bars, {1, 5, 10, 20}, cutoff).signal_strength;
  });
  run_benchmark("marine_dynamics_large_history", observations, iterations, samples, compiler, kraken::estimate_marine_dynamics_workload_metrics(observations, true), [&] {
    return kraken::compute_marine_dynamics(bars, cutoff, 0.0, 1.0, 5, 20).composite_dynamics_risk;
  });
  run_benchmark("calibration_large_history", observations, iterations, samples, compiler, kraken::estimate_calibration_workload_metrics(reference.size(), evaluation.size()), [&] {
    return kraken::calibrate_distance(reference, evaluation, cutoff).confidence;
  });
  run_benchmark("regime_large_history", observations, iterations, samples, compiler, kraken::estimate_regime_workload_metrics(reference.size(), evaluation.size(), 4U), [&] {
    return kraken::classify_regime(reference, evaluation, {1, 5, 10, 20}, cutoff).regime_score;
  });
  return 0;
}
