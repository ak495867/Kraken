#pragma once

#include <string>
#include <vector>

namespace kraken {

struct ResearchConfig {
  int schema_version;
  std::vector<int> sonar_horizons;
  int minimum_points;
  int reference_minimum_points;
  int evaluation_minimum_points;
  double reference_liquidity;
  double drag_scale;
  int fast_window;
  int slow_window;
  double calibration_decay;
  double forecast_coverage;
};

ResearchConfig default_research_config();
ResearchConfig migrate_research_config(const ResearchConfig& config);
ResearchConfig parse_research_config(const std::string& document);
std::string serialize_research_config(const ResearchConfig& config);
void validate_research_config(const ResearchConfig& config);

}
