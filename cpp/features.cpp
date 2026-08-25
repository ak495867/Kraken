#include "kraken_core/features.hpp"
#include "kraken_core/numeric.hpp"

#include <cmath>

namespace kraken::detail {

std::vector<double> log_returns(const std::vector<Bar>& bars) {
  std::vector<double> values;
  if (bars.size() < 2) {
    return values;
  }
  values.reserve(bars.size() - 1);
  for (std::size_t index = 1; index < bars.size(); ++index) {
    values.push_back(std::log(bars[index].close / bars[index - 1].close));
  }
  return values;
}

std::vector<double> volatility_values(const std::vector<Bar>& bars) {
  std::vector<double> values;
  values.reserve(bars.size());
  for (const auto& bar : bars) {
    values.push_back(bar.realized_volatility);
  }
  return values;
}

std::vector<double> log_liquidity_values(const std::vector<Bar>& bars) {
  std::vector<double> values;
  values.reserve(bars.size());
  for (const auto& bar : bars) {
    values.push_back(std::log1p(bar.liquidity));
  }
  return values;
}

std::vector<double> liquidity_changes(const std::vector<Bar>& bars) {
  std::vector<double> values;
  if (bars.size() < 2) {
    return values;
  }
  values.reserve(bars.size() - 1);
  for (std::size_t index = 1; index < bars.size(); ++index) {
    values.push_back(std::log1p(bars[index].liquidity) - std::log1p(bars[index - 1].liquidity));
  }
  return values;
}

FeatureSummary summarize(const std::vector<Bar>& bars) {
  const auto returns = log_returns(bars);
  const auto volatility = volatility_values(bars);
  const auto liquidity = log_liquidity_values(bars);
  const auto liquidity_delta = liquidity_changes(bars);
  return {
      mean(returns),
      standard_deviation(returns),
      mean(volatility),
      standard_deviation(volatility),
      mean(liquidity),
      standard_deviation(liquidity),
      correlation(returns, liquidity_delta),
  };
}

}
