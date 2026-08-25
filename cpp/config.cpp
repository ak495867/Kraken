#include "kraken_core/config.hpp"
#include "kraken_core/numeric.hpp"

#include <algorithm>
#include <cctype>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

namespace {

std::string trim(const std::string& value) {
  const auto first = std::find_if_not(value.begin(), value.end(), [](unsigned char character) { return std::isspace(character) != 0; });
  const auto last = std::find_if_not(value.rbegin(), value.rend(), [](unsigned char character) { return std::isspace(character) != 0; }).base();
  return first >= last ? std::string{} : std::string(first, last);
}

int parse_int(const std::string& value, const std::string& key) {
  std::size_t consumed = 0;
  try {
    const int result = std::stoi(value, &consumed);
    if (consumed != value.size()) {
      throw std::invalid_argument("invalid integer");
    }
    return result;
  } catch (const std::exception&) {
    throw std::invalid_argument("Configuration key " + key + " must be an integer");
  }
}

double parse_double(const std::string& value, const std::string& key) {
  std::size_t consumed = 0;
  try {
    const double result = std::stod(value, &consumed);
    if (consumed != value.size() || !kraken::detail::is_finite(result)) {
      throw std::invalid_argument("invalid number");
    }
    return result;
  } catch (const std::exception&) {
    throw std::invalid_argument("Configuration key " + key + " must be a finite number");
  }
}

std::vector<int> parse_horizons(const std::string& value) {
  std::vector<int> result;
  std::stringstream stream(value);
  std::string item;
  while (std::getline(stream, item, ',')) {
    const std::string cleaned = trim(item);
    if (cleaned.empty()) {
      throw std::invalid_argument("Configuration sonar_horizons must not contain empty values");
    }
    result.push_back(parse_int(cleaned, "sonar_horizons"));
  }
  return result;
}

std::string serialize_horizons(const std::vector<int>& horizons) {
  std::ostringstream stream;
  for (std::size_t index = 0; index < horizons.size(); ++index) {
    if (index > 0) {
      stream << ',';
    }
    stream << horizons[index];
  }
  return stream.str();
}

std::unordered_map<std::string, std::string> parse_entries(const std::string& document) {
  std::unordered_map<std::string, std::string> entries;
  std::stringstream lines(document);
  std::string line;
  while (std::getline(lines, line)) {
    const std::string cleaned = trim(line);
    if (cleaned.empty()) {
      continue;
    }
    const std::size_t separator = cleaned.find('=');
    if (separator == std::string::npos || cleaned.find('=', separator + 1) != std::string::npos) {
      throw std::invalid_argument("Configuration lines must contain exactly one equals separator");
    }
    const std::string key = trim(cleaned.substr(0, separator));
    const std::string value = trim(cleaned.substr(separator + 1));
    if (key.empty() || value.empty() || !entries.emplace(key, value).second) {
      throw std::invalid_argument("Configuration keys and values must be non-empty and unique");
    }
  }
  return entries;
}

void require_exact_keys(const std::unordered_map<std::string, std::string>& entries, const std::vector<std::string>& required) {
  for (const auto& key : required) {
    if (entries.find(key) == entries.end()) {
      throw std::invalid_argument("Configuration is missing required key " + key);
    }
  }
  if (entries.size() != required.size()) {
    throw std::invalid_argument("Configuration contains unknown keys");
  }
}

kraken::ResearchConfig parse_v1(const std::unordered_map<std::string, std::string>& entries) {
  const std::vector<std::string> required = {
      "schema_version", "sonar_horizons", "minimum_points", "reference_minimum_points", "evaluation_minimum_points", "reference_liquidity", "drag_scale", "fast_window", "slow_window",
  };
  require_exact_keys(entries, required);
  return {
      parse_int(entries.at("schema_version"), "schema_version"),
      parse_horizons(entries.at("sonar_horizons")),
      parse_int(entries.at("minimum_points"), "minimum_points"),
      parse_int(entries.at("reference_minimum_points"), "reference_minimum_points"),
      parse_int(entries.at("evaluation_minimum_points"), "evaluation_minimum_points"),
      parse_double(entries.at("reference_liquidity"), "reference_liquidity"),
      parse_double(entries.at("drag_scale"), "drag_scale"),
      parse_int(entries.at("fast_window"), "fast_window"),
      parse_int(entries.at("slow_window"), "slow_window"),
      0.0,
      0.0,
  };
}

kraken::ResearchConfig parse_v2(const std::unordered_map<std::string, std::string>& entries) {
  const std::vector<std::string> required = {
      "schema_version", "sonar_horizons", "minimum_points", "reference_minimum_points", "evaluation_minimum_points", "reference_liquidity", "drag_scale", "fast_window", "slow_window", "calibration_decay", "forecast_coverage",
  };
  require_exact_keys(entries, required);
  return {
      parse_int(entries.at("schema_version"), "schema_version"),
      parse_horizons(entries.at("sonar_horizons")),
      parse_int(entries.at("minimum_points"), "minimum_points"),
      parse_int(entries.at("reference_minimum_points"), "reference_minimum_points"),
      parse_int(entries.at("evaluation_minimum_points"), "evaluation_minimum_points"),
      parse_double(entries.at("reference_liquidity"), "reference_liquidity"),
      parse_double(entries.at("drag_scale"), "drag_scale"),
      parse_int(entries.at("fast_window"), "fast_window"),
      parse_int(entries.at("slow_window"), "slow_window"),
      parse_double(entries.at("calibration_decay"), "calibration_decay"),
      parse_double(entries.at("forecast_coverage"), "forecast_coverage"),
  };
}

}

namespace kraken {

ResearchConfig default_research_config() {
  return {2, {1, 5, 10}, 4, 6, 4, 0.0, 1.0, 5, 20, 0.25, 0.90};
}

void validate_research_config(const ResearchConfig& config) {
  if (config.schema_version != 2) {
    throw std::invalid_argument("Research configuration must be migrated to schema_version 2 before validation");
  }
  if (config.sonar_horizons.empty()) {
    throw std::invalid_argument("Configuration sonar_horizons must contain at least one horizon");
  }
  std::vector<int> deduplicated = config.sonar_horizons;
  std::sort(deduplicated.begin(), deduplicated.end());
  if (std::adjacent_find(deduplicated.begin(), deduplicated.end()) != deduplicated.end() || std::any_of(config.sonar_horizons.begin(), config.sonar_horizons.end(), [](int horizon) { return horizon <= 0; })) {
    throw std::invalid_argument("Configuration sonar_horizons must contain unique positive integers");
  }
  if (config.minimum_points < 4 || config.reference_minimum_points < 6 || config.evaluation_minimum_points < 4) {
    throw std::invalid_argument("Configuration minimum-point constraints are below native safety requirements");
  }
  if (!detail::is_finite(config.reference_liquidity) || !detail::is_finite(config.drag_scale) || config.reference_liquidity < 0.0 || config.drag_scale < 0.0) {
    throw std::invalid_argument("Configuration liquidity and drag scale must be finite non-negative values");
  }
  if (config.fast_window <= 0 || config.slow_window <= config.fast_window) {
    throw std::invalid_argument("Configuration tidal windows must be positive and slow_window must exceed fast_window");
  }
  if (!detail::is_finite(config.calibration_decay) || config.calibration_decay < 0.0 || config.calibration_decay > 1.0) {
    throw std::invalid_argument("Configuration calibration_decay must be finite and within [0, 1]");
  }
  if (!detail::is_finite(config.forecast_coverage) || config.forecast_coverage <= 0.0 || config.forecast_coverage >= 1.0) {
    throw std::invalid_argument("Configuration forecast_coverage must be finite and within (0, 1)");
  }
}

ResearchConfig migrate_research_config(const ResearchConfig& config) {
  if (config.schema_version == 2) {
    validate_research_config(config);
    return config;
  }
  if (config.schema_version != 1) {
    throw std::invalid_argument("Unsupported research configuration schema_version");
  }
  ResearchConfig migrated{
      2,
      config.sonar_horizons,
      config.minimum_points,
      config.reference_minimum_points,
      config.evaluation_minimum_points,
      config.reference_liquidity,
      config.drag_scale,
      config.fast_window,
      config.slow_window,
      0.25,
      0.90,
  };
  validate_research_config(migrated);
  return migrated;
}

ResearchConfig parse_research_config(const std::string& document) {
  const auto entries = parse_entries(document);
  const auto schema_iterator = entries.find("schema_version");
  if (schema_iterator == entries.end()) {
    throw std::invalid_argument("Configuration is missing required key schema_version");
  }
  const int schema_version = parse_int(schema_iterator->second, "schema_version");
  if (schema_version == 1) {
    return migrate_research_config(parse_v1(entries));
  }
  if (schema_version == 2) {
    ResearchConfig config = parse_v2(entries);
    validate_research_config(config);
    return config;
  }
  throw std::invalid_argument("Unsupported research configuration schema_version");
}

std::string serialize_research_config(const ResearchConfig& config) {
  const ResearchConfig canonical = migrate_research_config(config);
  std::ostringstream output;
  output << "schema_version=" << canonical.schema_version << '\n';
  output << "sonar_horizons=" << serialize_horizons(canonical.sonar_horizons) << '\n';
  output << "minimum_points=" << canonical.minimum_points << '\n';
  output << "reference_minimum_points=" << canonical.reference_minimum_points << '\n';
  output << "evaluation_minimum_points=" << canonical.evaluation_minimum_points << '\n';
  output << "reference_liquidity=" << canonical.reference_liquidity << '\n';
  output << "drag_scale=" << canonical.drag_scale << '\n';
  output << "fast_window=" << canonical.fast_window << '\n';
  output << "slow_window=" << canonical.slow_window << '\n';
  output << "calibration_decay=" << canonical.calibration_decay << '\n';
  output << "forecast_coverage=" << canonical.forecast_coverage << '\n';
  return output.str();
}

}
