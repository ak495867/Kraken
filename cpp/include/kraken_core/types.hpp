#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace kraken {

struct Bar {
  std::int64_t timestamp_ms;
  std::int64_t available_at_ms;
  double close;
  double volume;
  double realized_volatility;
  double liquidity;
};

struct Echo {
  int horizon;
  double displacement;
  double strength;
  double anomaly_score;
};

struct ForecastBand {
  int horizon;
  double lower;
  double center;
  double upper;
  double coverage;
  int sample_count;
};

struct SonarResult {
  double signal_strength;
  double anomaly_score;
  std::vector<Echo> echoes;
  std::vector<ForecastBand> forecast_bands;
  std::string status;
};

struct DistanceCalibration {
  double return_distance;
  double volatility_distance;
  double liquidity_distance;
  double correlation_distance;
  double nearest_regime_distance;
  double regime_risk_uncertainty;
  double calibration_drift;
  double confidence;
};

struct RegimeResult {
  std::string regime;
  double regime_score;
  double confidence;
  double uncertainty;
  double calibration_drift;
  SonarResult sonar;
  DistanceCalibration calibration;
};

struct DragVolatilityAdjustment {
  double reference_liquidity;
  double flow_intensity;
  double drag_coefficient;
  double drag_pressure;
  double adjusted_volatility;
};

struct TidalCurrentResult {
  int fast_window;
  int slow_window;
  double fast_return;
  double slow_return;
  double current_strength;
  double directional_bias;
};

struct CavitationRiskResult {
  double liquidity_vacuum;
  double return_shock;
  double cavitation_score;
};

struct BuoyancyResilienceResult {
  double liquidity_resilience;
  double volatility_load;
  double buoyancy_score;
};

struct MarineDynamicsResult {
  DragVolatilityAdjustment drag;
  TidalCurrentResult tidal;
  CavitationRiskResult cavitation;
  BuoyancyResilienceResult buoyancy;
  double composite_dynamics_risk;
};

struct IntegrityIssue {
  std::string code;
  std::string severity;
  std::string message;
};

struct IntegrityReport {
  bool valid;
  std::int64_t decision_cutoff_ms;
  int input_count;
  int eligible_count;
  std::int64_t first_timestamp_ms;
  std::int64_t last_timestamp_ms;
  std::vector<IntegrityIssue> issues;
};

}
