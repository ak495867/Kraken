#include "kraken_core/core.hpp"
#include "kraken_core/numeric.hpp"
#include "kraken_core/validation.hpp"

#include <limits>
#include <stdexcept>

namespace kraken::detail {

std::vector<Bar> eligible(const std::vector<Bar>& bars, std::int64_t decision_cutoff_ms) {
  std::vector<Bar> result;
  result.reserve(bars.size());
  for (const auto& bar : bars) {
    if (bar.timestamp_ms <= decision_cutoff_ms && bar.available_at_ms <= decision_cutoff_ms) {
      result.push_back(bar);
    }
  }
  return result;
}

void require_valid(const IntegrityReport& report) {
  if (!report.valid) {
    std::string message = "Integrity validation failed";
    if (!report.issues.empty()) {
      message += ": " + report.issues.front().message;
    }
    throw std::invalid_argument(message);
  }
}

}

namespace kraken {

IntegrityReport inspect_integrity(const std::vector<Bar>& bars, std::int64_t decision_cutoff_ms, int minimum_points) {
  IntegrityReport report{true, decision_cutoff_ms, static_cast<int>(bars.size()), 0, 0, 0, {}};
  if (decision_cutoff_ms <= 0) {
    report.valid = false;
    report.issues.push_back({"invalid_cutoff", "error", "Decision cutoff must be a positive UTC Unix millisecond timestamp"});
  }
  if (minimum_points < 2) {
    report.valid = false;
    report.issues.push_back({"invalid_minimum_points", "error", "Minimum point count must be at least two"});
  }
  if (bars.empty()) {
    report.valid = false;
    report.issues.push_back({"empty_input", "error", "At least one market observation is required"});
    return report;
  }
  report.first_timestamp_ms = bars.front().timestamp_ms;
  report.last_timestamp_ms = bars.back().timestamp_ms;
  std::int64_t previous_timestamp = std::numeric_limits<std::int64_t>::min();
  for (const auto& bar : bars) {
    if (bar.available_at_ms < bar.timestamp_ms) {
      report.valid = false;
      report.issues.push_back({"availability_before_timestamp", "error", "available_at must not precede timestamp"});
      break;
    }
    if (bar.timestamp_ms > decision_cutoff_ms) {
      report.valid = false;
      report.issues.push_back({"future_timestamp", "error", "Input contains a market timestamp after the decision cutoff"});
      break;
    }
    if (bar.available_at_ms > decision_cutoff_ms) {
      report.valid = false;
      report.issues.push_back({"availability_leakage", "error", "Input contains a value unavailable at the decision cutoff"});
      break;
    }
    if (bar.timestamp_ms <= previous_timestamp) {
      report.valid = false;
      report.issues.push_back({"non_monotonic_timestamp", "error", "Observation timestamps must be strictly increasing"});
      break;
    }
    previous_timestamp = bar.timestamp_ms;
    if (!detail::is_finite(bar.close) || !detail::is_finite(bar.volume) || !detail::is_finite(bar.realized_volatility) || !detail::is_finite(bar.liquidity)) {
      report.valid = false;
      report.issues.push_back({"non_finite_feature", "error", "Market fields must be finite numeric values"});
      break;
    }
    if (bar.close <= 0.0 || bar.volume < 0.0 || bar.realized_volatility < 0.0 || bar.liquidity < 0.0) {
      report.valid = false;
      report.issues.push_back({"invalid_market_value", "error", "Close must be positive and volume, volatility, and liquidity must be non-negative"});
      break;
    }
    ++report.eligible_count;
  }
  if (report.eligible_count < minimum_points) {
    report.valid = false;
    report.issues.push_back({"insufficient_history", "error", "Insufficient eligible observations for the requested computation"});
  }
  return report;
}

}
