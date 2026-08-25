#include "kraken_core/core.hpp"
#include "kraken_core/numeric.hpp"

#include <cmath>

namespace kraken {

RegimeResult classify_regime(const std::vector<Bar>& reference, const std::vector<Bar>& evaluation, const std::vector<int>& horizons, std::int64_t decision_cutoff_ms) {
  const auto sonar = compute_sonar(evaluation, horizons, decision_cutoff_ms);
  const auto calibration = calibrate_distance(reference, evaluation, decision_cutoff_ms);
  const double anomaly_component = detail::clamp(std::erf(sonar.anomaly_score / std::sqrt(2.0)), 0.0, 1.0);
  const double score = detail::clamp(0.40 * anomaly_component + 0.40 * calibration.regime_risk_uncertainty + 0.20 * calibration.calibration_drift, 0.0, 1.0);
  std::string regime = "stable";
  if (score >= 0.99) {
    regime = "dislocated";
  } else if (score >= 0.95) {
    regime = "stressed";
  } else if (score >= 0.80) {
    regime = "transitional";
  }
  return {regime, score, calibration.confidence, calibration.regime_risk_uncertainty, calibration.calibration_drift, sonar, calibration};
}

RegimeResult classify_regime_with_config(const std::vector<Bar>& reference, const std::vector<Bar>& evaluation, std::int64_t decision_cutoff_ms, const ResearchConfig& config) {
  validate_research_config(config);
  const auto sonar = compute_sonar_with_config(evaluation, decision_cutoff_ms, config);
  const auto calibration = calibrate_distance_with_config(reference, evaluation, decision_cutoff_ms, config);
  const double anomaly_component = detail::clamp(std::erf(sonar.anomaly_score / std::sqrt(2.0)), 0.0, 1.0);
  const double score = detail::clamp(0.40 * anomaly_component + 0.40 * calibration.regime_risk_uncertainty + 0.20 * calibration.calibration_drift, 0.0, 1.0);
  std::string regime = "stable";
  if (score >= 0.99) {
    regime = "dislocated";
  } else if (score >= 0.95) {
    regime = "stressed";
  } else if (score >= 0.80) {
    regime = "transitional";
  }
  return {regime, score, calibration.confidence, calibration.regime_risk_uncertainty, calibration.calibration_drift, sonar, calibration};
}

}
