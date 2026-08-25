#include "kraken_core/core.hpp"

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

namespace py = pybind11;

PYBIND11_MODULE(_core, module) {
  module.doc() = "Deterministic Kraken quantitative research core";

  py::class_<kraken::Bar>(module, "Bar")
      .def(py::init<>())
      .def_readwrite("timestamp_ms", &kraken::Bar::timestamp_ms)
      .def_readwrite("available_at_ms", &kraken::Bar::available_at_ms)
      .def_readwrite("close", &kraken::Bar::close)
      .def_readwrite("volume", &kraken::Bar::volume)
      .def_readwrite("realized_volatility", &kraken::Bar::realized_volatility)
      .def_readwrite("liquidity", &kraken::Bar::liquidity);

  py::class_<kraken::ResearchConfig>(module, "ResearchConfig")
      .def(py::init<>())
      .def_readwrite("schema_version", &kraken::ResearchConfig::schema_version)
      .def_readwrite("sonar_horizons", &kraken::ResearchConfig::sonar_horizons)
      .def_readwrite("minimum_points", &kraken::ResearchConfig::minimum_points)
      .def_readwrite("reference_minimum_points", &kraken::ResearchConfig::reference_minimum_points)
      .def_readwrite("evaluation_minimum_points", &kraken::ResearchConfig::evaluation_minimum_points)
      .def_readwrite("reference_liquidity", &kraken::ResearchConfig::reference_liquidity)
      .def_readwrite("drag_scale", &kraken::ResearchConfig::drag_scale)
      .def_readwrite("fast_window", &kraken::ResearchConfig::fast_window)
      .def_readwrite("slow_window", &kraken::ResearchConfig::slow_window)
      .def_readwrite("calibration_decay", &kraken::ResearchConfig::calibration_decay)
      .def_readwrite("forecast_coverage", &kraken::ResearchConfig::forecast_coverage);

  py::class_<kraken::Echo>(module, "Echo")
      .def_readonly("horizon", &kraken::Echo::horizon)
      .def_readonly("displacement", &kraken::Echo::displacement)
      .def_readonly("strength", &kraken::Echo::strength)
      .def_readonly("anomaly_score", &kraken::Echo::anomaly_score);

  py::class_<kraken::ForecastBand>(module, "ForecastBand")
      .def_readonly("horizon", &kraken::ForecastBand::horizon)
      .def_readonly("lower", &kraken::ForecastBand::lower)
      .def_readonly("center", &kraken::ForecastBand::center)
      .def_readonly("upper", &kraken::ForecastBand::upper)
      .def_readonly("coverage", &kraken::ForecastBand::coverage)
      .def_readonly("sample_count", &kraken::ForecastBand::sample_count);

  py::class_<kraken::SonarResult>(module, "SonarResult")
      .def_readonly("signal_strength", &kraken::SonarResult::signal_strength)
      .def_readonly("anomaly_score", &kraken::SonarResult::anomaly_score)
      .def_readonly("echoes", &kraken::SonarResult::echoes)
      .def_readonly("forecast_bands", &kraken::SonarResult::forecast_bands)
      .def_readonly("status", &kraken::SonarResult::status);

  py::class_<kraken::DistanceCalibration>(module, "DistanceCalibration")
      .def_readonly("return_distance", &kraken::DistanceCalibration::return_distance)
      .def_readonly("volatility_distance", &kraken::DistanceCalibration::volatility_distance)
      .def_readonly("liquidity_distance", &kraken::DistanceCalibration::liquidity_distance)
      .def_readonly("correlation_distance", &kraken::DistanceCalibration::correlation_distance)
      .def_readonly("nearest_regime_distance", &kraken::DistanceCalibration::nearest_regime_distance)
      .def_readonly("regime_risk_uncertainty", &kraken::DistanceCalibration::regime_risk_uncertainty)
      .def_readonly("calibration_drift", &kraken::DistanceCalibration::calibration_drift)
      .def_readonly("confidence", &kraken::DistanceCalibration::confidence);

  py::class_<kraken::RegimeResult>(module, "RegimeResult")
      .def_readonly("regime", &kraken::RegimeResult::regime)
      .def_readonly("regime_score", &kraken::RegimeResult::regime_score)
      .def_readonly("confidence", &kraken::RegimeResult::confidence)
      .def_readonly("uncertainty", &kraken::RegimeResult::uncertainty)
      .def_readonly("calibration_drift", &kraken::RegimeResult::calibration_drift)
      .def_readonly("sonar", &kraken::RegimeResult::sonar)
      .def_readonly("calibration", &kraken::RegimeResult::calibration);

  py::class_<kraken::DragVolatilityAdjustment>(module, "DragVolatilityAdjustment")
      .def_readonly("reference_liquidity", &kraken::DragVolatilityAdjustment::reference_liquidity)
      .def_readonly("flow_intensity", &kraken::DragVolatilityAdjustment::flow_intensity)
      .def_readonly("drag_coefficient", &kraken::DragVolatilityAdjustment::drag_coefficient)
      .def_readonly("drag_pressure", &kraken::DragVolatilityAdjustment::drag_pressure)
      .def_readonly("adjusted_volatility", &kraken::DragVolatilityAdjustment::adjusted_volatility);

  py::class_<kraken::TidalCurrentResult>(module, "TidalCurrentResult")
      .def_readonly("fast_window", &kraken::TidalCurrentResult::fast_window)
      .def_readonly("slow_window", &kraken::TidalCurrentResult::slow_window)
      .def_readonly("fast_return", &kraken::TidalCurrentResult::fast_return)
      .def_readonly("slow_return", &kraken::TidalCurrentResult::slow_return)
      .def_readonly("current_strength", &kraken::TidalCurrentResult::current_strength)
      .def_readonly("directional_bias", &kraken::TidalCurrentResult::directional_bias);

  py::class_<kraken::CavitationRiskResult>(module, "CavitationRiskResult")
      .def_readonly("liquidity_vacuum", &kraken::CavitationRiskResult::liquidity_vacuum)
      .def_readonly("return_shock", &kraken::CavitationRiskResult::return_shock)
      .def_readonly("cavitation_score", &kraken::CavitationRiskResult::cavitation_score);

  py::class_<kraken::BuoyancyResilienceResult>(module, "BuoyancyResilienceResult")
      .def_readonly("liquidity_resilience", &kraken::BuoyancyResilienceResult::liquidity_resilience)
      .def_readonly("volatility_load", &kraken::BuoyancyResilienceResult::volatility_load)
      .def_readonly("buoyancy_score", &kraken::BuoyancyResilienceResult::buoyancy_score);

  py::class_<kraken::MarineDynamicsResult>(module, "MarineDynamicsResult")
      .def_readonly("drag", &kraken::MarineDynamicsResult::drag)
      .def_readonly("tidal", &kraken::MarineDynamicsResult::tidal)
      .def_readonly("cavitation", &kraken::MarineDynamicsResult::cavitation)
      .def_readonly("buoyancy", &kraken::MarineDynamicsResult::buoyancy)
      .def_readonly("composite_dynamics_risk", &kraken::MarineDynamicsResult::composite_dynamics_risk);

  py::class_<kraken::IntegrityIssue>(module, "IntegrityIssue")
      .def_readonly("code", &kraken::IntegrityIssue::code)
      .def_readonly("severity", &kraken::IntegrityIssue::severity)
      .def_readonly("message", &kraken::IntegrityIssue::message);

  py::class_<kraken::IntegrityReport>(module, "IntegrityReport")
      .def_readonly("valid", &kraken::IntegrityReport::valid)
      .def_readonly("decision_cutoff_ms", &kraken::IntegrityReport::decision_cutoff_ms)
      .def_readonly("input_count", &kraken::IntegrityReport::input_count)
      .def_readonly("eligible_count", &kraken::IntegrityReport::eligible_count)
      .def_readonly("first_timestamp_ms", &kraken::IntegrityReport::first_timestamp_ms)
      .def_readonly("last_timestamp_ms", &kraken::IntegrityReport::last_timestamp_ms)
      .def_readonly("issues", &kraken::IntegrityReport::issues);

  module.def("inspect_integrity", &kraken::inspect_integrity, py::arg("bars"), py::arg("decision_cutoff_ms"), py::arg("minimum_points") = 4);
  module.def("default_research_config", &kraken::default_research_config);
  module.def("migrate_research_config", &kraken::migrate_research_config, py::arg("config"));
  module.def("parse_research_config", &kraken::parse_research_config, py::arg("document"));
  module.def("serialize_research_config", &kraken::serialize_research_config, py::arg("config"));
  module.def("validate_research_config", &kraken::validate_research_config, py::arg("config"));
  module.def("compute_sonar", &kraken::compute_sonar, py::arg("bars"), py::arg("horizons"), py::arg("decision_cutoff_ms"));
  module.def("compute_sonar_with_config", &kraken::compute_sonar_with_config, py::arg("bars"), py::arg("decision_cutoff_ms"), py::arg("config"));
  module.def("calibrate_distance", &kraken::calibrate_distance, py::arg("reference"), py::arg("evaluation"), py::arg("decision_cutoff_ms"));
  module.def("calibrate_distance_with_config", &kraken::calibrate_distance_with_config, py::arg("reference"), py::arg("evaluation"), py::arg("decision_cutoff_ms"), py::arg("config"));
  module.def("classify_regime", &kraken::classify_regime, py::arg("reference"), py::arg("evaluation"), py::arg("horizons"), py::arg("decision_cutoff_ms"));
  module.def("classify_regime_with_config", &kraken::classify_regime_with_config, py::arg("reference"), py::arg("evaluation"), py::arg("decision_cutoff_ms"), py::arg("config"));
  module.def("compute_drag_volatility_adjustment", &kraken::compute_drag_volatility_adjustment, py::arg("bars"), py::arg("decision_cutoff_ms"), py::arg("reference_liquidity") = 0.0, py::arg("drag_scale") = 1.0);
  module.def("compute_tidal_current", &kraken::compute_tidal_current, py::arg("bars"), py::arg("decision_cutoff_ms"), py::arg("fast_window") = 5, py::arg("slow_window") = 20);
  module.def("compute_cavitation_risk", &kraken::compute_cavitation_risk, py::arg("bars"), py::arg("decision_cutoff_ms"));
  module.def("compute_buoyancy_resilience", &kraken::compute_buoyancy_resilience, py::arg("bars"), py::arg("decision_cutoff_ms"));
  module.def("compute_marine_dynamics", &kraken::compute_marine_dynamics, py::arg("bars"), py::arg("decision_cutoff_ms"), py::arg("reference_liquidity") = 0.0, py::arg("drag_scale") = 1.0, py::arg("fast_window") = 5, py::arg("slow_window") = 20);
  module.def("compute_marine_dynamics_with_config", &kraken::compute_marine_dynamics_with_config, py::arg("bars"), py::arg("decision_cutoff_ms"), py::arg("config"));
}
