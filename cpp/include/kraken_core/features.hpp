#pragma once

#include "kraken_core/types.hpp"

#include <vector>

namespace kraken::detail {

struct FeatureSummary {
  double return_mean;
  double return_deviation;
  double volatility_mean;
  double volatility_deviation;
  double liquidity_mean;
  double liquidity_deviation;
  double correlation_value;
};

std::vector<double> log_returns(const std::vector<Bar>& bars);
std::vector<double> volatility_values(const std::vector<Bar>& bars);
std::vector<double> log_liquidity_values(const std::vector<Bar>& bars);
std::vector<double> liquidity_changes(const std::vector<Bar>& bars);
FeatureSummary summarize(const std::vector<Bar>& bars);

}
