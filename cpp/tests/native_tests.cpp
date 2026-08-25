#include "kraken_core/config.hpp"
#include "kraken_core/core.hpp"
#include "kraken_core/instrumentation.hpp"

#include <cmath>
#include <exception>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

std::vector<kraken::Bar> make_bars(int count) {
  std::vector<kraken::Bar> bars;
  bars.reserve(static_cast<std::size_t>(count));
  for (int index = 0; index < count; ++index) {
    const double value = static_cast<double>(index);
    bars.push_back({
        1'700'000'000'000LL + static_cast<std::int64_t>(index) * 86'400'000LL,
        1'700'000'000'000LL + static_cast<std::int64_t>(index) * 86'400'000LL,
        100.0 + 0.20 * value + std::sin(value / 5.0),
        1'000'000.0 + 5'000.0 * value,
        0.01 + 0.002 * std::abs(std::sin(value / 9.0)),
        2'000'000.0 + 15'000.0 * value,
    });
  }
  return bars;
}

void require(bool condition, const std::string& message) {
  if (!condition) {
    throw std::runtime_error(message);
  }
}

template <typename Callable>
void require_throws(Callable callable, const std::string& message) {
  try {
    callable();
  } catch (const std::invalid_argument&) {
    return;
  }
  throw std::runtime_error(message);
}

void test_integrity_rejects_unavailable_bar() {
  auto bars = make_bars(12);
  const std::int64_t cutoff = bars.back().timestamp_ms;
  bars.back().available_at_ms = cutoff + 1;
  const auto report = kraken::inspect_integrity(bars, cutoff, 4);
  require(!report.valid, "Integrity report must reject unavailable observations");
  require(!report.issues.empty() && report.issues.front().code == "availability_leakage", "Integrity report must expose availability leakage");
}

void test_sonar_is_deterministic() {
  const auto bars = make_bars(48);
  const std::int64_t cutoff = bars.back().timestamp_ms;
  const auto first = kraken::compute_sonar(bars, {1, 5, 10}, cutoff);
  const auto second = kraken::compute_sonar(bars, {1, 5, 10}, cutoff);
  require(first.signal_strength == second.signal_strength, "Sonar signal strength must be deterministic");
  require(first.anomaly_score == second.anomaly_score, "Sonar anomaly score must be deterministic");
  require(first.echoes.size() == 3 && second.echoes.size() == 3, "Sonar must preserve all requested horizons");
}

void test_calibration_and_regime_bounds() {
  const auto bars = make_bars(56);
  const std::vector<kraken::Bar> reference(bars.begin(), bars.begin() + 32);
  const std::vector<kraken::Bar> evaluation(bars.begin() + 32, bars.end());
  const std::int64_t cutoff = bars.back().timestamp_ms;
  const auto calibration = kraken::calibrate_distance(reference, evaluation, cutoff);
  const auto regime = kraken::classify_regime(reference, evaluation, {1, 5, 10}, cutoff);
  require(calibration.confidence >= 0.0 && calibration.confidence <= 1.0, "Calibration confidence must be bounded");
  require(regime.regime_score >= 0.0 && regime.regime_score <= 1.0, "Regime score must be bounded");
}

void test_dynamics_bounds() {
  const auto bars = make_bars(48);
  const auto result = kraken::compute_marine_dynamics(bars, bars.back().timestamp_ms, 0.0, 1.0, 5, 20);
  require(result.composite_dynamics_risk >= 0.0 && result.composite_dynamics_risk <= 1.0, "Composite dynamics risk must be bounded");
  require(result.cavitation.cavitation_score >= 0.0 && result.cavitation.cavitation_score <= 1.0, "Cavitation score must be bounded");
  require(result.buoyancy.buoyancy_score >= 0.0 && result.buoyancy.buoyancy_score <= 1.0, "Buoyancy score must be bounded");
}

void test_versioned_configuration() {
  const auto config = kraken::default_research_config();
  const auto document = kraken::serialize_research_config(config);
  const auto parsed = kraken::parse_research_config(document);
  require(parsed.schema_version == 2, "Configuration schema version must roundtrip to v2");
  require(parsed.sonar_horizons == config.sonar_horizons, "Configuration horizons must roundtrip");
  const auto migrated = kraken::parse_research_config("schema_version=1\nsonar_horizons=1,5,10\nminimum_points=4\nreference_minimum_points=6\nevaluation_minimum_points=4\nreference_liquidity=0\ndrag_scale=1\nfast_window=5\nslow_window=20\n");
  require(migrated.schema_version == 2, "Schema v1 configuration must migrate to v2");
  require(migrated.calibration_decay == 0.25 && migrated.forecast_coverage == 0.90, "Schema v1 migration must apply deterministic v2 defaults");
  require_throws([] { kraken::parse_research_config("schema_version=3\nsonar_horizons=1\nminimum_points=4\nreference_minimum_points=6\nevaluation_minimum_points=4\nreference_liquidity=0\ndrag_scale=1\nfast_window=5\nslow_window=20\n"); }, "Unsupported schema must be rejected");
}

void test_workload_instrumentation() {
  const auto sonar = kraken::estimate_sonar_workload_metrics(100U, 3U);
  require(sonar.input_bar_copy_count == 0U && sonar.input_bar_copy_bytes == 0U, "Sonar instrumentation must show no copied Bar history");
  require(sonar.temporary_double_buffer_count == 1U && sonar.temporary_double_buffer_bytes == 99U * sizeof(double), "Sonar instrumentation must report its return buffer");
  const auto dynamics = kraken::estimate_marine_dynamics_workload_metrics(100U, true);
  require(dynamics.input_bar_copy_count == 0U && dynamics.input_bar_copy_bytes == 0U, "Marine dynamics instrumentation must show no copied Bar history");
  require(dynamics.temporary_double_buffer_count == 8U && dynamics.temporary_double_buffer_bytes == 698U * sizeof(double), "Marine dynamics instrumentation must report deterministic feature buffers");
  const auto calibration = kraken::estimate_calibration_workload_metrics(60U, 40U);
  require(calibration.input_bar_copy_count == 0U && calibration.input_bar_copy_bytes == 0U, "Calibration instrumentation must show no copied Bar history");
  require(calibration.temporary_double_buffer_count == 9U && calibration.temporary_double_buffer_bytes == 455U * sizeof(double), "Calibration instrumentation must report deterministic feature buffers");
  const auto regime = kraken::estimate_regime_workload_metrics(60U, 40U, 3U);
  require(regime.input_bar_copy_count == 0U && regime.input_bar_copy_bytes == 0U, "Regime instrumentation must show no copied Bar history");
  require(regime.temporary_double_buffer_count == 10U && regime.temporary_double_buffer_bytes == 494U * sizeof(double), "Regime instrumentation must compose calibration and sonar feature buffers");
}

}

int main() {
  try {
    test_integrity_rejects_unavailable_bar();
    test_sonar_is_deterministic();
    test_calibration_and_regime_bounds();
    test_dynamics_bounds();
    test_versioned_configuration();
    test_workload_instrumentation();
  } catch (const std::exception& error) {
    std::cerr << error.what() << '\n';
    return 1;
  }
  return 0;
}
